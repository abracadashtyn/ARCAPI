import datetime
import json

import click
import requests
from flask import current_app

from app import redis_cache
from app.home_stats import compute_format_top_pokemon, compute_pokemon_usage_change, HOME_CACHE_TTL_SECONDS
from app.tasks import bp


@bp.cli.group()
def cacheops():
    pass

def delete_keys(match_pattern):
    cursor = 0
    while True:
        cursor, keys = redis_cache.scan(cursor=cursor, match=match_pattern, count=100)
        if len(keys) > 0:
            redis_cache.delete(*keys)
            click.echo(f"deleted keys {keys}")
        if cursor == 0:
            return

def get_matching_keys(match_pattern):
    cursor = 0
    key_list = []
    while True:
        cursor, keys = redis_cache.scan(cursor=cursor, match=match_pattern, count=100)
        key_list.extend(keys)
        if cursor == 0:
            return key_list

@cacheops.command('clear-all')
def clear():
    redis_cache.flushall()

@cacheops.command('clear-pokemon')
def clear_pokemon():
    delete_keys("pokemon_stats:v*")

@cacheops.command('clear-format')
@click.option('--format_id', '-f', type=int)
def clear_format(format_id):
    delete_keys(f"format_stats:v1:{format_id}:*")
    delete_keys(f"format_pokemon_stats:v1:{format_id}:*")
    delete_keys(f"pokemon_usage_change:v1:{format_id}:*")
    delete_keys(f"best_matches_prev_day:{format_id}")

def clear_best_matches():
    delete_keys(f"best_matches_prev_day:*")

@cacheops.command('echo-keys')
def echo_keys():
    cursor = 0
    while True:
        cursor, keys = redis_cache.scan(cursor=cursor, match="*", count=100)
        for key in keys:
            print(key)
        if cursor == 0:
            return

@cacheops.command('warm')
@click.pass_context
@click.option('--format_id', '-f', type=int)
@click.option('--api_version', '-v', type=int, default=1, help="Version of the API to warm the cache for.")
def warm(ctx, format_id, api_version):
    """Refresh the cache for a format IN PLACE: the home-page aggregates are computed here in the CLI process and
    overwrite their keys, so users keep being served the previous values while new ones are computed. (The old
    delete-then-recompute-via-HTTP flow left the home page uncached for minutes per cycle and tied up API workers.)"""
    if api_version == 0:
        click.echo("WARNING: api v0 is deprecated. No cache is maintained for these endpoints any longer.")
        delete_keys("*:v0:*")
        return

    if format_id is None:
        format_id = current_app.config.get('CURRENT_FORMAT_ID')

    # format_stats (format record + match counts) is cheap to recompute on demand; just drop it
    delete_keys(f"format_stats:v1:{format_id}:*")

    # 1. top pokemon list for the format (all-time), overwritten in place
    top_pokemon_list = []
    try:
        top_pokemon_list = compute_format_top_pokemon(format_id, None)
        redis_cache.setex(f"format_pokemon_stats:v{api_version}:{format_id}:all", HOME_CACHE_TTL_SECONDS,
                          json.dumps(top_pokemon_list))
        click.echo(f"Refreshed top pokemon list for format {format_id} ({len(top_pokemon_list)} pokemon)")
    except Exception as e:
        click.echo(f"ERROR: failed to refresh top pokemon list for format {format_id}: {e}")

    # 2. usage change for every lookback window the clients use (default 'week' first — it is on the home page)
    for lookback in ['week', '30days', 'day']:
        try:
            usage = compute_pokemon_usage_change(format_id, lookback)
            redis_cache.setex(f"pokemon_usage_change:v{api_version}:{format_id}:{lookback}", HOME_CACHE_TTL_SECONDS,
                              json.dumps(usage))
            click.echo(f"Refreshed pokemon usage change for format {format_id}, lookback {lookback}")
        except Exception as e:
            click.echo(f"ERROR: failed to refresh pokemon usage change for format {format_id}, lookback {lookback}: {e}")

    # 3. home page top 50 matches of the last 24 hours (v1 only)
    if api_version == 1:
        try:
            # imported here: the namespace module registers itself with the API on import
            from app.api.v1.matches_namespace import SearchMatches
            now = datetime.datetime.now()
            best_prev = SearchMatches.perform_search({
                "format_id": format_id,
                "order_by": "rating",
                "time_range": {"start": (now - datetime.timedelta(hours=24)).timestamp(), "end": now.timestamp()},
                "limit": 50,
                "page": 1,
            })
            if best_prev.get('success') is True:
                best_prev.pop('pagination', None)
                redis_cache.setex(f"best_matches_prev_day:{format_id}", HOME_CACHE_TTL_SECONDS, json.dumps(best_prev))
                click.echo(f"Refreshed best matches of previous day for format {format_id}")
            else:
                click.echo(f"ERROR: best matches search for format {format_id} did not succeed: {best_prev}")
        except Exception as e:
            click.echo(f"ERROR: failed to refresh best matches of previous day for format {format_id}: {e}")

    # 4. per-pokemon detail for the most used pokemon, via the API as before. If this format is the current one,
    # cache 50 pokemon; only 10 for non-current formats as less people will be looking for that data.
    top_pokemon_count = 50 if format_id == current_app.config.get('CURRENT_FORMAT_ID') else 10
    pokemon_cache_keys = get_matching_keys(f"pokemon_stats:v{api_version}:{format_id}:*")
    pokemon_ids = [int(x.split(':')[-2]) for x in pokemon_cache_keys]
    try:
        for pokemon_id, _count in top_pokemon_list[:top_pokemon_count]:
            # delete old key
            if pokemon_id in pokemon_ids:
                delete_keys(f"pokemon_stats:v{api_version}:{format_id}:{pokemon_id}:*")
                pokemon_ids.remove(pokemon_id)

            # call endpoint to repopulate cache
            pokemon_url = f"{current_app.config['BASE_URL']}/api/v{api_version}/pokemon/{pokemon_id}?format_id={format_id}"
            click.echo(f"Calling {pokemon_url} to warm cache for pokemon {pokemon_id}")
            pokemon_detail = requests.get(pokemon_url)
            if pokemon_detail.status_code != 200:
                click.echo(f"ERROR: web request to warm cache for pokemon {pokemon_id} failed. "
                           f"{pokemon_detail.status_code}: {pokemon_detail.text}")

        # delete any old pokemon cache keys that weren't removed as part of the above
        if len(pokemon_ids) > 0:
            click.echo(f"Will remove outdated cache keys for pokemon with ids {pokemon_ids}")
            for pokemon_id in pokemon_ids:
                delete_keys(f"pokemon_stats:v{api_version}:{format_id}:{pokemon_id}:*")
    except Exception as e:
        click.echo(f"ERROR: exception thrown while warming per-pokemon cache: {e}")

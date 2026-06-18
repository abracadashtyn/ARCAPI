import click
import requests
from flask import current_app

from app import redis_cache
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
def clear_format():
    delete_keys("format_stats:v*")
    delete_keys("format_pokemon_stats:v1:*")
    delete_keys("pokemon_usage_change:v1:*:*")

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
    if api_version == 0:
        click.echo("WARNING: api v0 is deprecated. No cache is maintained for these endpoints any longer.")
        delete_keys("*:v0:*")
        return

    if format_id is None:
        format_id = current_app.config.get('CURRENT_FORMAT_ID')
    
    #delete old format keys
    ctx.invoke(clear_format)

    # recreate cache for format endpoint. If this format is the current one, cache 50 pokemon. Will only cache 10
    # for non-current pokemon as less people will be looking for that data.
    #top_pokemon_count = 50 if format_id == current_app.config.get('CURRENT_FORMAT_ID') else 10
    # TODO revert after last Reg I tournament in May
    top_pokemon_count = 50 if format_id in (2,3) else 10
    format_url = f"{current_app.config['BASE_URL']}/api/v{api_version}/formats/{format_id}?top_pokemon_count={top_pokemon_count}"
    click.echo(f"Calling {format_url} to warm format cache")
    try:
        format_detail = requests.get(format_url)
        if format_detail.status_code == 200:
            # calculate pokemon usage change for the default lookback period (will do other lookback periods at a later
            # time, but this one is used on the website's home page
            usage_url = f"{current_app.config['BASE_URL']}/api/v{api_version}/pokemon/usage?format_id={format_id}"
            click.echo(f"Calling {usage_url} to warm pokemon usage cache")
            usage_details = requests.get(usage_url)
            if not usage_details.ok:
                click.echo(f"Failed to populate pokemon usage cache: {usage_details.status_code}: {usage_details.text}")

            pokemon_cache_keys = get_matching_keys(f"pokemon_stats:v{api_version}:{format_id}:*")
            pokemon_ids = [int(x.split(':')[-2]) for x in pokemon_cache_keys]

            format_detail = format_detail.json()
            for pokemon in format_detail['data']['top_pokemon']:
                # delete old key
                if pokemon['id'] in pokemon_ids:
                    delete_keys(f"pokemon_stats:v{api_version}:{format_id}:{pokemon['id']}:*")
                    pokemon_ids.remove(pokemon['id'])

                # call endpoint to repopulate cache
                pokemon_url = f"{current_app.config['BASE_URL']}/api/v{api_version}/pokemon/{pokemon['id']}?format_id={format_id}"
                click.echo(f"Calling {pokemon_url} to warm cache for pokemon {pokemon['name']}")
                pokemon_detail = requests.get(pokemon_url)
                if pokemon_detail.status_code != 200:
                    click.echo(f"ERROR: web request to warm cache for pokemon {pokemon['name']} failed. "
                               f"{pokemon_detail.status_code}: {pokemon_detail.text}")

            # delete any old pokemon cache keys that weren't removed as part of the above
            if len(pokemon_ids) > 0:
                click.echo(f"Will remove outdated cache keys for pokemon with ids {pokemon_ids}")
                for pokemon_id in pokemon_ids:
                    delete_keys(f"pokemon_stats:v{api_version}:{format_id}:{pokemon_id}:*")
        else:
            click.echo(f"ERROR: web request to warm cache for format {format_id} failed. "
                       f"{format_detail.status_code}: {format_detail.text}")

        if api_version == 1:
            # delete old cache key first
            redis_cache.delete(f"best_matches_prev_day:{format_id}")
            # warm cache for new endpoint 'best_previous_day' that only exists in v1
            best_prev_day_url = f"{current_app.config['BASE_URL']}/api/v{api_version}/matches/best_previous_day?format_id={format_id}"
            click.echo(f"Calling {best_prev_day_url} to warm cache for home page top 50 matches in last 24 hours")
            best_prev_response = requests.get(best_prev_day_url)
            if best_prev_response.status_code != 200:
                click.echo(f"ERROR: web request to warm cache for home page failed. "
                           f"{best_prev_response.status_code}: {best_prev_response.text} ")


        # populate usage stats for non default lookback periods
        for lookback in ['30days', 'day']:
            usage_url = f"{current_app.config['BASE_URL']}/api/v{api_version}/pokemon/usage?format_id={format_id}&lookback={lookback}"
            click.echo(f"Calling {usage_url} to warm pokemon usage cache for lookback {lookback}")
            usage_details = requests.get(usage_url)
            if not usage_details.ok:
                click.echo(
                    f"Failed to populate pokemon usage cache: {usage_details.status_code}: {usage_details.text}")

    except Exception as e:
        click.echo(f"ERROR: exception thrown while warming cache: {e}")
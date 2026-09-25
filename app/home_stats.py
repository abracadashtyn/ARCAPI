"""Aggregations behind the home page (format top pokemon, pokemon usage change).

Shared by the API endpoints and the cache warmer so the warmer can compute
values in-process and overwrite cache keys in place — no delete-then-recompute
window during which users hit uncached, slow requests.

Query shape matters here: driving from `matches` (indexed by format_id +
upload_time) and grouping by the raw pm_pokemon.pokemon_id lets MySQL touch
only the format's rows via covering indexes. Grouping by a CASE over the
`pokemon` table (the previous shape) made the optimizer start from `pokemon`
and walk the entire pm_pokemon table for every request — 75-150s per query on
production versus ~1s for this shape. The cosmetic-form -> base-species
collapse happens in Python afterwards over ~1.4k rows.
"""
import datetime
import logging

from sqlalchemy import func, case

from app import db
from app.models import Match, PlayerMatch, PlayerMatchPokemon, Pokemon

# Home-page keys are refreshed in place by the warmer every ingestion cycle
# (~30 min); the TTL only matters if warming fails, in which case serving
# slightly stale data beats an on-demand recompute under load.
HOME_CACHE_TTL_SECONDS = 7200


def base_species_map():
    """Map every pokemon id to the id its usage should be counted under
    (cosmetic-only forms roll up into their base species)."""
    rows = db.session.execute(
        db.select(Pokemon.id, Pokemon.is_cosmetic_only, Pokemon.base_species_id)
    ).all()
    return {
        pokemon_id: base_species_id if (is_cosmetic_only and base_species_id is not None) else pokemon_id
        for pokemon_id, is_cosmetic_only, base_species_id in rows
    }


def _format_pokemon_query(format_id):
    return db.select(
        PlayerMatchPokemon.pokemon_id,
    ).select_from(
        Match
    ).join(
        PlayerMatch, PlayerMatch.match_id == Match.id
    ).join(
        PlayerMatchPokemon, PlayerMatchPokemon.player_match_id == PlayerMatch.id
    ).where(
        Match.format_id == format_id
    ).group_by(
        PlayerMatchPokemon.pokemon_id
    ).prefix_with('STRAIGHT_JOIN', dialect='mysql')


def compute_format_top_pokemon(format_id, lookback_time=None):
    """Usage counts per (base) pokemon in a format, most used first, as
    [[pokemon_id, count], ...] — the shape stored under format_pokemon_stats."""
    stmt = _format_pokemon_query(format_id).add_columns(func.count().label('pokemon_count'))
    if lookback_time is not None:
        stmt = stmt.where(Match.upload_time >= int(lookback_time.timestamp()))

    base_of = base_species_map()
    counts = {}
    for pokemon_id, pokemon_count in db.session.execute(stmt).all():
        base_id = base_of.get(pokemon_id, pokemon_id)
        counts[base_id] = counts.get(base_id, 0) + int(pokemon_count)
    return sorted(([pokemon_id, count] for pokemon_id, count in counts.items()), key=lambda x: -x[1])


def usage_period_bounds(lookback):
    """(current_period_end, prev_period_end) unix timestamps for a lookback
    window; raises ValueError for an unknown window."""
    now = datetime.datetime.now()
    if lookback == 'day':
        days = 1
    elif lookback == 'week':
        days = 7
    elif lookback == '30days':
        days = 30
    else:
        raise ValueError(lookback)
    return (
        int((now - datetime.timedelta(days=days)).timestamp()),
        int((now - datetime.timedelta(days=2 * days)).timestamp()),
    )


def _usage_entry(pokemon_id, prev_count, current_count, prev_total, current_total):
    prev_percent = prev_count / prev_total * 100 if prev_total else 0.0
    current_percent = current_count / current_total * 100 if current_total else 0.0
    record = Pokemon.query.get(pokemon_id).to_dict()
    record['prev_period_team_count'] = prev_count
    record['prev_period_team_percent'] = float(round(prev_percent, 2))
    record['current_period_team_count'] = current_count
    record['current_period_team_percent'] = float(round(current_percent, 2))
    record['usage_change_percent'] = float(round(current_percent - prev_percent, 2))
    return record


def compute_pokemon_usage_change(format_id, lookback):
    """Full /pokemon/usage response body: the 10 biggest usage-share risers and
    fallers between the previous and current lookback period."""
    current_period_end, prev_period_end = usage_period_bounds(lookback)

    current_period_match_count = db.session.query(func.count('*')).select_from(Match).filter(
        Match.format_id == format_id,
        Match.upload_time >= current_period_end,
    ).scalar()
    prev_period_match_count = db.session.query(func.count('*')).select_from(Match).filter(
        Match.format_id == format_id,
        Match.upload_time < current_period_end,
        Match.upload_time >= prev_period_end,
    ).scalar()
    current_period_total_teams = current_period_match_count * 2
    prev_period_total_teams = prev_period_match_count * 2

    stmt = _format_pokemon_query(format_id).add_columns(
        func.sum(case((Match.upload_time >= current_period_end, 1), else_=0)).label('current_team_count'),
        func.sum(case((Match.upload_time < current_period_end, 1), else_=0)).label('prev_team_count'),
    ).where(
        Match.upload_time >= prev_period_end
    )

    base_of = base_species_map()
    totals = {}
    for pokemon_id, current_team_count, prev_team_count in db.session.execute(stmt).all():
        base_id = base_of.get(pokemon_id, pokemon_id)
        current, prev = totals.get(base_id, (0, 0))
        totals[base_id] = (current + int(current_team_count or 0), prev + int(prev_team_count or 0))

    def change_percent(item):
        current, prev = item[1]
        prev_percent = prev / prev_period_total_teams * 100 if prev_period_total_teams else 0.0
        current_percent = current / current_period_total_teams * 100 if current_period_total_teams else 0.0
        return current_percent - prev_percent

    ranked = sorted(
        ((pokemon_id, counts) for pokemon_id, counts in totals.items() if counts[0] > 0 or counts[1] > 0),
        key=change_percent,
        reverse=True,
    )

    response = {
        'success': True,
        'data': {
            'current_period_total_teams': current_period_total_teams,
            'prev_period_total_teams': prev_period_total_teams,
            'increased': [],
            'decreased': [],
        }
    }
    for pokemon_id, (current, prev) in ranked[:10]:
        response['data']['increased'].append(
            _usage_entry(pokemon_id, prev, current, prev_period_total_teams, current_period_total_teams))
    for pokemon_id, (current, prev) in reversed(ranked[-10:]):
        response['data']['decreased'].append(
            _usage_entry(pokemon_id, prev, current, prev_period_total_teams, current_period_total_teams))

    logging.info(f"Computed pokemon usage change for format {format_id}, lookback {lookback}")
    return response

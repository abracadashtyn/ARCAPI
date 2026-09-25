"""Server-rendered link previews (Open Graph / Twitter Card tags) for the web app.

The web app at arcvgc.com is a Compose-for-Wasm single-page app served as one static
index.html, so link unfurlers (Discord, Twitter/X, Slack, iMessage, ...) - which read
<meta> tags out of the raw HTML and never run JavaScript - only ever see the generic
site-wide tags. nginx routes requests from those crawlers here instead (see
deploy/arcvgc.conf in the frontend repo), and this blueprint renders a tiny HTML page
whose tags describe the linked battle, Pokemon, or player. Real browsers never reach
these routes.

nginx rewrites `/<path>?<query>` to `/preview/<path>?<query>`, so the path handled here
mirrors the web app's own URL scheme (docs/navigation.md in the frontend repo):

    /battle/{id}            legacy battle link
    /<anything>?battle={id} battle detail opened from any page (takes priority)
    /pokemon/{id}           battles featuring a Pokemon
    /player/{name}          a player's battles

Anything else (home, search, usage, favorites, settings) gets the site-wide defaults.
A lookup failure of any kind also falls back to the defaults - a generic card is
better than an error page in a chat client.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, current_app, make_response, render_template, request
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from app import db
from app.models import Match, Player, PlayerMatch, PlayerMatchPokemon, Pokemon

bp = Blueprint('preview', __name__, url_prefix='/preview')

SITE_NAME = 'ARC'
DEFAULT_DESCRIPTION = 'Browse and search data from Showdown replays'
# Same asset index.html uses for the site-wide card; the ?v= is its cache-buster.
LOGO_PATH = '/arc-logo.png?v=2'
# Crawlers re-fetch on their own schedule anyway; this just keeps repeated shares of the
# same link from hitting the database every time.
CACHE_MAX_AGE_SECONDS = 300


@dataclass
class PreviewMeta:
    title: str
    description: str
    image_url: str
    url: str
    # 'summary_large_image' suits the wide logo; 'summary' suits a square sprite.
    twitter_card: str = 'summary_large_image'


@bp.route('/', defaults={'path': ''})
@bp.route('/<path:path>')
def preview(path):
    meta = build_preview(path)
    response = make_response(render_template('preview.html', preview=meta, site_name=SITE_NAME))
    response.headers['Cache-Control'] = f'public, max-age={CACHE_MAX_AGE_SECONDS}'
    return response


def build_preview(path):
    """Resolves the web-app path (plus the current request's query string) to card metadata."""
    segments = [segment for segment in path.split('/') if segment]
    try:
        battle_id = request.args.get('battle', type=int)
        if battle_id is None and len(segments) == 2 and segments[0] == 'battle':
            battle_id = _parse_int(segments[1])
        if battle_id is not None:
            match_record = _load_match(battle_id)
            if match_record is not None:
                return battle_preview(match_record, _page_url(path))

        if len(segments) == 2 and segments[0] == 'pokemon':
            pokemon_id = _parse_int(segments[1])
            pokemon_record = db.session.get(Pokemon, pokemon_id) if pokemon_id is not None else None
            if pokemon_record is not None:
                return pokemon_preview(pokemon_record, _page_url(path))

        if len(segments) == 2 and segments[0] == 'player':
            player_record = Player.query.filter_by(name=segments[1]).first()
            if player_record is not None:
                return player_preview(player_record, _page_url(path))
    except SQLAlchemyError as e:
        logging.error(f'Falling back to the default link preview for /{path}: {e}')

    return default_preview(_page_url(path))


def default_preview(url):
    return PreviewMeta(
        title=SITE_NAME,
        description=DEFAULT_DESCRIPTION,
        image_url=_logo_url(),
        url=url,
    )


def battle_preview(match_record, url):
    """'{Format}: {Player 1} vs. {Player 2}' with rating, winner, game number, date, and both teams."""
    players = list(match_record.players)
    format_name = match_record.format.formatted_name or match_record.format.name
    title = f"{format_name}: {' vs. '.join(pm.player.name for pm in players)}"

    facts = [f'Rated {match_record.rating}' if match_record.rating is not None else 'Unrated']
    winner = next((pm.player.name for pm in players if pm.won_match), None)
    if winner is not None:
        facts.append(f'{winner} won')
    if match_record.format.has_series and match_record.position_in_set:
        facts.append(f'Game {match_record.position_in_set}')
    facts.append(_format_date(match_record.upload_time))

    lines = [' · '.join(facts)]
    for pm in players:
        team = ', '.join(entry.pokemon.name for entry in pm.pokemon)
        if team:
            lines.append(f'{pm.player.name}: {team}')

    return PreviewMeta(
        title=title,
        description='\n'.join(lines),
        image_url=_logo_url(),
        url=url,
    )


def pokemon_preview(pokemon_record, url):
    return PreviewMeta(
        title=pokemon_record.name,
        description=f'Battles featuring {pokemon_record.name} on {SITE_NAME}',
        image_url=pokemon_record.get_image_url(),
        url=url,
        twitter_card='summary',
    )


def player_preview(player_record, url):
    # Player.to_dict() loads every PlayerMatch row to count them; a COUNT is enough here.
    match_count = db.session.query(func.count(PlayerMatch.id)) \
        .filter(PlayerMatch.player_id == player_record.id) \
        .scalar() or 0
    noun = 'battle' if match_count == 1 else 'battles'
    return PreviewMeta(
        title=player_record.name,
        description=f'{match_count} {noun} on {SITE_NAME}',
        image_url=_logo_url(),
        url=url,
    )


def _load_match(match_id):
    return Match.query \
        .options(
            joinedload(Match.format),
            selectinload(Match.players).joinedload(PlayerMatch.player),
            selectinload(Match.players).selectinload(PlayerMatch.pokemon).joinedload(PlayerMatchPokemon.pokemon),
        ) \
        .filter_by(id=match_id) \
        .first()


def _page_url(path):
    """The public web-app URL the crawler asked for, i.e. the request URL minus the /preview prefix."""
    url = f"{current_app.config['BASE_URL']}/{quote(path, safe='/')}"
    if request.query_string:
        url = f"{url}?{request.query_string.decode('utf-8', 'replace')}"
    return url


def _logo_url():
    return f"{current_app.config['BASE_URL']}{LOGO_PATH}"


def _format_date(upload_time):
    # Same local-time interpretation as Match.to_dict(); no %-d so it stays portable.
    dt = datetime.fromtimestamp(upload_time)
    return f'{dt:%b} {dt.day}, {dt.year}'


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

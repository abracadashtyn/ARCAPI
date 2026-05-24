import datetime
import json
import logging
import uuid
from collections import Counter

from flask import request, current_app
from flask_restx import Namespace, fields, Resource
from sqlalchemy import text, case, func, or_, distinct
from sqlalchemy.exc import SQLAlchemyError

from app import db, redis_cache
from app.api.v1 import api_v1
from app.api.v1.abilities_namespace import ability_model
from app.api.v1.errors import APIError, error_response, NotFoundError
from app.api.v1.items_namespace import item_model
from app.api.v1.moves_namespace import move_model
from app.api.v1.pagination import pagination_model, paginate_query
from app.api.v1.players_namespace import player_model
from app.api.v1.types_namespace import pokemon_type_model
from app.models import Pokemon, PokemonType, Item, Match, Move, Player, PlayerMatchPokemon, PlayerMatch

pokemon_ns = Namespace('Pokemon', description="Endpoints related to pokemon information.")
api_v1.add_namespace(pokemon_ns, path='/pokemon')

pokemon_base_species_model = api_v1.model('PokemonReference', {
    'id': fields.Integer(example=19),
    'name': fields.String(example="Rattata"),
    'pokedex_number': fields.Integer(example=19),
    'image_url': fields.String(example="https://arcvgc.com/static/images/pokemon/rattata.png"),
})
pokemon_model = api_v1.model('PokemonModel', {
    'id': fields.Integer(example=1034),
    'pokedex_number': fields.Integer(example=19),
    'name': fields.String(example="Rattata-Alola"),
    'tier': fields.String(example="Illegal", description="As defined by Pokemon Showdown/Smogon, see "
                                                         "https://www.smogon.com/bw/articles/bw_tiers for more information."),
    'types': fields.List(fields.Nested(pokemon_type_model)),
    'image_url': fields.String(example="https://arcvgc.com/static/images/pokemon/rattata-alola.png"),
    'base_species': fields.Nested(pokemon_base_species_model, allow_null=True,
                                  description='Base form if this is a variant (e.g., Alolan forms)')
})
pokemon_list_response = api_v1.model('PokemonListResponse', {
    'success': fields.Boolean(example=True),
    'data': fields.List(fields.Nested(pokemon_model)),
    'pagination': fields.Nested(pagination_model)
})
"""Fetch a list of all Pokemon"""
@pokemon_ns.route('/')
class PokemonList(Resource):
    @pokemon_ns.doc('list_pokemon')
    @pokemon_ns.param('page', description='Page number', type='integer', default=1)
    @pokemon_ns.param('limit', description='Items per page', type='integer', default=50)
    @pokemon_ns.param('exclude_illegal', type='boolean', default=True,
                      description='Filters list so no pokemon from the illegal tier appear in results')
    @pokemon_ns.param('type_ids', type='string',
                      description='Comma separated list of type IDs to filter pokemon on. Will include all pokemon who '
                                  'match any of these types.')
    @pokemon_ns.param(name='name', description='Name of pokemon (full or partial) to filter results by', type='string')
    @pokemon_ns.response(500, 'Internal server error', error_response)
    @pokemon_ns.marshal_with(pokemon_list_response, code=200)
    def get(self):
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        query = Pokemon.query \
            .filter(Pokemon.is_cosmetic_only == False) \
            .order_by(Pokemon.pokedex_number, Pokemon.name)

        if 'exclude_illegal' in request.args and (
                request.args['exclude_illegal'] is True or request.args['exclude_illegal'].lower() == "true"):
            query = query.filter(Pokemon.tier != "Illegal")

        if 'type_ids' in request.args:
            try:
                type_ids = [int(id.strip()) for id in request.args.get('type_ids').split(',')]
            except ValueError:
                api_v1.abort(400, 'Invalid type_ids')
            query = query.filter(Pokemon.types.any(PokemonType.id.in_(type_ids)))

        if 'name' in request.args:
            search_string = request.args['name']
            if '%' not in search_string:
                search_string = f"%{search_string}%"
            query = query.filter(Pokemon.name.like(search_string))

        try:
            response, data = paginate_query(query, page, limit)
            return response
        except SQLAlchemyError as e:
            raise APIError(f'Error querying database for pokemon: {e}', code='DB_ERROR', status=500)


pokemon_form_model = api_v1.model('PokemonForm', {
    'id': fields.Integer,
    'pokedex_number': fields.Integer,
    'name': fields.String,
    'tier': fields.String,
    'types': fields.List(fields.Nested(pokemon_type_model)),
    'is_cosmetic_only': fields.Boolean(),
    'image_url': fields.String,
})
item_frequency_model = api_v1.inherit('ItemFrequency', item_model, {
    'count': fields.Integer,
})
tera_type_frequency_model = api_v1.inherit('TeraTypeFrequency', pokemon_type_model, {
    'count': fields.Integer,
})
move_frequency_model = api_v1.inherit('MoveFrequency', move_model, {
    'count': fields.Integer,
})
ability_frequency_model = api_v1.inherit('AbilityFrequency', ability_model, {
    'count': fields.Integer,
})
teammate_frequency_model = api_v1.inherit('TeammateFrequency', pokemon_base_species_model, {
    'count': fields.Integer,
})
top_players_model = api_v1.inherit('TopPlayers', player_model, {
    'top_5_matches': fields.Nested(api_v1.model('TopMatch', {
        'id': fields.Integer(example=1),
        'showdown_id': fields.String(example="gen9vgc2026regibo3-2565555555"),
        'upload_time': fields.DateTime(example="2026-01-01T17:30:00"),
        'rating': fields.Integer(example=1000),
    })),
    'ranked_win_count': fields.Integer(example=10),
    'avg_rating': fields.Float(example=1367.4),
    'max_rating': fields.Integer(example=1500),
    'min_rating': fields.Integer(example=1000),
})
pokemon_detail_model = api_v1.inherit('PokemonDetail', pokemon_model, {
    'forms': fields.List(fields.Nested(pokemon_form_model)),
    'match_count': fields.Integer,
    'match_percent': fields.Float,
    'team_count': fields.Integer,
    'team_percent': fields.Float,
    'top_items': fields.List(fields.Nested(item_frequency_model)),
    'top_tera_types': fields.List(fields.Nested(tera_type_frequency_model)),
    'top_moves': fields.List(fields.Nested(move_frequency_model)),
    'top_abilities': fields.List(fields.Nested(ability_frequency_model)),
    'top_teammates': fields.List(fields.Nested(teammate_frequency_model)),
    'top_players': fields.List(fields.Nested(top_players_model)),
})
pokemon_detail_response = api_v1.model('PokemonDetailResponse', {
    'success': fields.Boolean,
    'data': fields.Nested(pokemon_detail_model)
})
"""Fetch details on on particular pokemon by ID, including usage statistics for the current format (or other format 
specified via request parameter)"""
@pokemon_ns.route('/<int:pokemon_id>')
class PokemonDetail(Resource):
    @pokemon_ns.doc('get_pokemon')
    @pokemon_ns.param('format_id', description='Format ID', type='integer')
    @pokemon_ns.param('lookback', type='str', enum=['all', 'week', 'day', '30days'], default='all')
    @pokemon_ns.response(404, 'Pokemon not found', error_response)
    @pokemon_ns.response(500, 'Internal server error', error_response)
    @pokemon_ns.marshal_with(pokemon_detail_response, code=200)
    def get(self, pokemon_id):
        logging.basicConfig(level=logging.INFO)

        # get format
        format_id = request.args.get('format_id', type=int) if 'format_id' in request.args \
            else current_app.config['CURRENT_FORMAT_ID']

        # calculate the period of time to look for matches in this format
        lookback = request.args.get('lookback', 'all', type=str)
        lookback_time = None
        if lookback == 'day':
            lookback_time = datetime.datetime.now() - datetime.timedelta(days=1)
        elif lookback == 'week':
            lookback_time = datetime.datetime.now() - datetime.timedelta(days=7)
        elif lookback == '30days':
            lookback_time = datetime.datetime.now() - datetime.timedelta(days=30)

        # see if a cached response for this pokemon already exists, and if so, return that instead of recomputing stats
        cache_key = f"pokemon_stats:v1:{format_id}:{pokemon_id}:{lookback}"
        cached_response = redis_cache.get(cache_key)
        if cached_response is not None:
            cached_response = json.loads(cached_response)
            if cached_response['success'] is True:
                logging.info(f"Serving PokemonDetail response for pokemon id {pokemon_id} from cache.")
                return cached_response

        # if no cached response exists already, calculate that and store it
        logging.info(f"No cached PokemonDetail response found; computing stats for pokemon with id {pokemon_id}")
        try:
            pokemon_record = Pokemon.query.filter_by(id=pokemon_id).first()
        except SQLAlchemyError as e:
            raise APIError(f'Error querying database for pokemon with ID {pokemon_id}: {e}', code='DB_ERROR', status=500)
        if not pokemon_record:
            raise NotFoundError('Pokemon with ID {pokemon_id} not found')

        response = {
            'success': True,
            'data': pokemon_record.to_dict()
        }

        # check if this pokemon has any forms, and if so, add to response
        try:
            forms = Pokemon.query.filter(Pokemon.base_species_id == pokemon_record.id).all()
            if len(forms) > 0:
                response['data']['forms'] = []
                for form in forms:
                    form_dict = form.to_dict()
                    if form_dict['is_cosmetic_only']:
                        form_dict.pop('types')
                    response['data']['forms'].append(form_dict)
        except SQLAlchemyError as e:
            api_v1.abort(500, f'Error querying database for pokemon with ID {pokemon_id}: {e}')

        # create temporary table to pre-filter out only the relevant player_match_pokemon records for this format and
        # pokemon. Required as mysql was not materializing cte and queries were lagging.
        table_name = f"temp_filtered_pmp_{uuid.uuid4().hex[:8]}"
        try:
            pokemon_ids = [pokemon_id]
            # check for ids of cosmetic children to filter the query on
            children = Pokemon.query.filter(
                Pokemon.base_species_id == pokemon_id,
                Pokemon.is_cosmetic_only == True
            ).all()
            pokemon_ids += [x.id for x in children]

            temp_table_statement = f"""
                CREATE TEMPORARY TABLE {table_name} AS
                SELECT 
                    pmp.id,
                    pmp.player_match_id,
                    pm.player_id,
                    pm.won_match,
                    m.id as match_id,
                    m.rating,
                    pmp.ability_id,
                    pmp.item_id,
                    pmp.tera_type_id,
                    pmp.move_1_id,
                    pmp.move_2_id,
                    pmp.move_3_id,
                    pmp.move_4_id
                FROM pm_pokemon pmp
                JOIN player_matches pm ON pmp.player_match_id = pm.id
                JOIN matches m ON pm.match_id = m.id
                WHERE 
                    m.format_id = :format_id AND 
                    pmp.pokemon_id IN :pokemon_ids
            """
            temp_table_params = {
                'table_name': table_name,
                'format_id': format_id,
                'pokemon_ids': tuple(pokemon_ids),
            }
            if lookback_time:
                temp_table_statement += f" AND m.upload_time > :lookback"
                temp_table_params['lookback'] = int(lookback_time.timestamp())

            db.session.execute(text(temp_table_statement), temp_table_params)

            # find number of matches this mon appears in on at least one team
            match_count = db.session.execute(text(f"""
                SELECT
                    COUNT(DISTINCT pmp.match_id)
                FROM 
                    {table_name} as pmp
            """)).scalar()
            response['data']['match_count'] = match_count
            total_matches = Match.query.filter_by(format_id=format_id).count()
            percent_used = match_count / total_matches * 100
            response['data']['match_percent'] = percent_used

            # find count and percentage of teams this mon is used in
            team_count = db.session.execute(text(f"""
                SELECT 
                    count(distinct pmp.player_match_id) 
                FROM
                    {table_name} as pmp
            """)).scalar()
            response['data']['team_count'] = team_count
            team_percent = team_count / (total_matches * 2) * 100
            response['data']['team_percent'] = team_percent

            # find the top ranked matches where this mon was on the winning team (and the associated player data for
            # the winning player)
            response['data']['top_players'] = []
            top_players = db.session.execute(text(f"""
                SELECT 
                    pmp.player_id,
                    GROUP_CONCAT(pmp.match_id ORDER BY pmp.rating DESC) as match_ids,
                    COUNT(pmp.match_id) as ranked_win_count,
                    avg(pmp.rating) as avg_rating,
                    max(pmp.rating) as max_rating,
                    min(pmp.rating) as min_rating
                FROM
                    {table_name} as pmp
                WHERE
                    pmp.won_match = True
                    AND pmp.rating >= 1000
                GROUP BY
                    pmp.player_id
                ORDER BY 
                    MAX(pmp.rating) DESC,
                    ranked_win_count DESC
                LIMIT 6;
            """)).mappings().all()

            for player in top_players:
                player_record = Player.query.get(player['player_id'])
                player_response = {
                    'id': player_record.id,
                    'name': player_record.name,
                    'ranked_win_count': player['ranked_win_count'],
                    'avg_rating': float(round(player['avg_rating'], 1)),
                    'max_rating': player['max_rating'],
                    'min_rating': player['min_rating'],
                    'top_5_matches': []
                }
                won_match_list = player['match_ids'].split(',')
                for won_match_id in won_match_list[:5]:
                    match_record = Match.query.get(won_match_id)
                    player_response['top_5_matches'].append({
                        'id': match_record.id,
                        'showdown_id': match_record.showdown_id,
                        'upload_time': match_record.get_upload_datetime(),
                        'rating': match_record.rating,
                    })

                response['data']['top_players'].append(player_response)

            # aggregate the top 6 most common items used
            most_common_items = db.session.execute(text(f"""
                SELECT 
                    i.id,
                    i.name,
                    count(*) as item_count
                FROM
                    {table_name} as pmp
                JOIN
                    items as i on pmp.item_id = i.id
                GROUP BY
                    i.id,
                    i.name
                ORDER BY
                    item_count DESC
                LIMIT 6 
            """)).fetchall()
            response['data']['top_items'] = []
            for item in most_common_items:
                response['data']['top_items'].append({
                    'id': item[0],
                    'name': item[1],
                    'image_url': Item.image_url_from_name(item[1]),
                    'count': item[2],
                })

            # aggregate top 6 most common tera types
            most_common_tera = db.session.execute(text(f"""
                SELECT 
                    t.id,
                    t.name,
                    count(*) as tera_type_count
                FROM
                    {table_name} as pmp
                JOIN
                     pokemon_types as t on pmp.tera_type_id = t.id
                GROUP BY
                    t.id,
                    t.name
                ORDER BY
                    tera_type_count DESC
                LIMIT 6
            """)).fetchall()
            response['data']['top_tera_types'] = []
            for type in most_common_tera:
                response['data']['top_tera_types'].append({
                    'id': type[0],
                    'name': type[1],
                    'image_url': PokemonType.tera_image_url_from_name(type[1]),
                    'count': type[2],
                })

            # aggregate top 6 most common abilities
            most_common_abilities = db.session.execute(text(f"""
                SELECT
                    a.id,
                    a.name,
                    count(*) as ability_count
                FROM
                    {table_name} as pmp
                JOIN
                    abilities as a on pmp.ability_id = a.id
                GROUP BY
                    a.id,
                    a.name
                ORDER BY
                    ability_count DESC
                LIMIT 6
            """)).fetchall()
            response['data']['top_abilities'] = []
            for ability in most_common_abilities:
                response['data']['top_abilities'].append({
                    'id': ability[0],
                    'name': ability[1],
                    'count': ability[2],
                })

            # aggregate top 6 most common moves. Each column must be queried individually and combined in python, as the
            # temp_filtered_pmp temporary table can't be reused in the same query, and when implemented as a cte it was not
            # being materialized but rather reconstructed 4 separate times, resulting in slow query times for mons with
            # many records in the PlayerMatchPokemon table.
            move_1 = db.session.execute(text(
                f"""SELECT move_1_id, count(*) as move_count FROM {table_name} WHERE move_1_id IS NOT NULL GROUP BY move_1_id""")).fetchall()
            move_2 = db.session.execute(text(
                f"""SELECT move_2_id, count(*) as move_count FROM {table_name} WHERE move_2_id IS NOT NULL GROUP BY move_2_id""")).fetchall()
            move_3 = db.session.execute(text(
                f"""SELECT move_3_id, count(*) as move_count FROM {table_name} WHERE move_3_id IS NOT NULL GROUP BY move_3_id""")).fetchall()
            move_4 = db.session.execute(text(
                f"""SELECT move_4_id, count(*) as move_count FROM {table_name} WHERE move_4_id IS NOT NULL GROUP BY move_4_id""")).fetchall()

            most_common_moves = Counter(dict(move_1))
            most_common_moves.update(dict(move_2))
            most_common_moves.update(dict(move_3))
            most_common_moves.update(dict(move_4))

            response['data']['top_moves'] = []
            for move in most_common_moves.most_common(6):
                response['data']['top_moves'].append({
                    'id': move[0],
                    'name': Move.query.get(move[0]).name,
                    'count': move[1],
                })

            # aggregate top 6 most common teammates
            most_common_teammates = db.session.execute(text(f"""
                SELECT
                    CASE WHEN p.is_cosmetic_only=1 THEN p.base_species_id ELSE p.id END as pokemon_id,
                    count(*) as pokemon_count
                FROM
                    {table_name} as tmp
                JOIN
                    pm_pokemon as pmp on pmp.player_match_id = tmp.player_match_id
                JOIN
                    pokemon as p on pmp.pokemon_id = p.id
                WHERE
                    pmp.pokemon_id NOT IN :pokemon_ids
                GROUP BY
                    CASE WHEN p.is_cosmetic_only=1 THEN p.base_species_id ELSE p.id END
                ORDER BY
                    pokemon_count DESC
                LIMIT 6
            """), {'pokemon_ids': tuple(pokemon_ids)}).fetchall()
            response['data']['top_teammates'] = []
            for team in most_common_teammates:
                mon_record = Pokemon.query.get(team[0]).to_dict()
                mon_record['count'] = team[1]
                response['data']['top_teammates'].append(mon_record)

            # store response in cache for faster retrieval next time. Cache duration is 35 min, but will be manually
            # invalidated by ingestion method when new data is added
            redis_cache.setex(cache_key, 2100, json.dumps(response))
            logging.info(f"Stored response in cache with key {cache_key}")

        except Exception as e:
            logging.error(f"Error constructing stats for pokemon with id {pokemon_id}: {e}")
            raise APIError(f'Error constructing stats for pokemon with id {pokemon_id}', code='PYTHON_ERROR',
                           status=500)

        finally:
            db.session.execute(text(f"DROP TEMPORARY TABLE IF EXISTS {table_name}"))

        return response

pokemon_usage_model = api_v1.inherit('PokemonUsage', pokemon_base_species_model, {
    'id': fields.Integer(example=19),
    'name': fields.String(example="Rattata"),
    'pokedex_number': fields.Integer(example=19),
    'image_url': fields.String(example="https://arcvgc.com/static/images/pokemon/rattata.png"),
    'prev_period_team_count': fields.Integer(example=3791),
    'prev_period_team_percent': fields.Float(example=24.70),
    'current_period_team_count': fields.Integer(example=3965),
    'current_period_team_percent': fields.Float(example=17.90),
    'usage_change_percent': fields.Float(example=6.80),
})
usage_data_model = api_v1.model('UsageData', {
    'prev_period_total_teams': fields.Integer(example=22791),
    'current_period_total_teams': fields.Integer(example=22839),
    'increased': fields.List(fields.Nested(pokemon_usage_model)),
    'decreased': fields.List(fields.Nested(pokemon_usage_model)),
})
pokemon_usage_response = api_v1.model('PokemonListResponse', {
    'success': fields.Boolean(example=True),
    'data': fields.Nested(usage_data_model),
})
@pokemon_ns.route('/usage')
class PokemonUsageChange(Resource):
    @pokemon_ns.doc('usage_')
    @pokemon_ns.param('format_id', description='Format ID', type='integer')
    @pokemon_ns.param('lookback', type='str', enum=['week', 'day', '30days'], default='week')
    @pokemon_ns.response(500, 'Internal server error', error_response)
    @pokemon_ns.marshal_with(pokemon_usage_response, code=200)
    def get(self):
        logging.basicConfig(level=logging.INFO)

        format_id = request.args.get('format_id', type=int) if 'format_id' in request.args \
            else current_app.config['CURRENT_FORMAT_ID']
        lookback = request.args.get('lookback', 'week')

        # see if a cached response for this pokemon already exists, and if so, return that instead of recomputing stats
        cache_key = f"pokemon_usage_change:v1:{format_id}:{lookback}"
        cached_response = redis_cache.get(cache_key)
        if cached_response is not None:
            cached_response = json.loads(cached_response)
            if cached_response['success'] is True:
                logging.info(f"Serving PokemonUsageChange response from cache.")
                return cached_response
        logging.info(f"No cached PokemonUsageChange response found; computing stats now.")

        # get all the matches from the last week in this format
        current_period_end = None
        prev_period_end = None
        if lookback == 'day':
            current_period_end = datetime.datetime.now() - datetime.timedelta(days=1)
            prev_period_end = datetime.datetime.now() - datetime.timedelta(days=2)
        elif lookback == 'week':
            current_period_end = datetime.datetime.now() - datetime.timedelta(days=7)
            prev_period_end = datetime.datetime.now() - datetime.timedelta(days=14)
        elif lookback == '30days':
            current_period_end = datetime.datetime.now() - datetime.timedelta(days=30)
            prev_period_end = datetime.datetime.now() - datetime.timedelta(days=60)
        else:
            raise APIError(f"Error calculating usage stats for lookback window '{lookback}'",
                           code='PYTHON_ERROR',  status=500)

        current_period_end = int(current_period_end.timestamp())
        prev_period_end = int(prev_period_end.timestamp())

        current_period_match_count = db.session.query(
            func.count('*')
        ).select_from(
            Match
        ).filter(
            Match.format_id == format_id,
            Match.upload_time >= current_period_end
        ).scalar()
        current_period_total_teams = current_period_match_count * 2

        prev_period_match_count = db.session.query(
            func.count('*')
        ).select_from(
            Match
        ).filter(
            Match.format_id == format_id,
            Match.upload_time < current_period_end,
            Match.upload_time >= prev_period_end
        ).scalar()
        prev_period_total_teams = prev_period_match_count * 2

        counts_base_query = db.select(
            case((Pokemon.is_cosmetic_only == True, Pokemon.base_species_id), else_=Pokemon.id).label("pokemon_id"),
            func.count(distinct(case((Match.upload_time >= current_period_end, PlayerMatch.id), else_=None))).label('current_team_count'),
            func.count(distinct(case((Match.upload_time.between(prev_period_end, current_period_end), PlayerMatch.id), else_=None))).label('prev_team_count'),
        ).select_from(
            PlayerMatchPokemon
        ).join(
            PlayerMatch, PlayerMatchPokemon.player_match_id == PlayerMatch.id
        ).join(
            Match, PlayerMatch.match_id == Match.id
        ).join(
            Pokemon, PlayerMatchPokemon.pokemon_id == Pokemon.id
        ).filter(
            Match.format_id == format_id,
            Match.upload_time >= prev_period_end
        ).group_by(
            case((Pokemon.is_cosmetic_only == True, Pokemon.base_species_id), else_=Pokemon.id),
        ).subquery()

        top_used = db.session.execute(db.select(
            counts_base_query.c.pokemon_id,
            counts_base_query.c.prev_team_count,
            (counts_base_query.c.prev_team_count / prev_period_total_teams * 100).label('prev_team_percent'),
            counts_base_query.c.current_team_count,
            (counts_base_query.c.current_team_count / current_period_total_teams * 100).label('current_team_percent'),
            (counts_base_query.c.current_team_count - counts_base_query.c.prev_team_count).label('usage_change_count'),
            ((counts_base_query.c.current_team_count / current_period_total_teams * 100) - (counts_base_query.c.prev_team_count / prev_period_total_teams * 100)).label('usage_change_percent'),
        ).filter(
            or_(counts_base_query.c.prev_team_count > 0, counts_base_query.c.current_team_count > 0)
        ).order_by(
            ((counts_base_query.c.current_team_count / current_period_total_teams * 100) - (counts_base_query.c.prev_team_count / prev_period_total_teams * 100)).desc()
        )).mappings().all()

        response = {
            'success': True,
            'data': {
                'current_period_total_teams': current_period_total_teams,
                'prev_period_total_teams': prev_period_total_teams,
                'increased': [],
                'decreased': []
            }
        }

        for top_positive in top_used[:10]:
            pokemon_record = Pokemon.query.get(top_positive['pokemon_id']).to_dict()
            pokemon_record['prev_period_team_count'] = top_positive['prev_team_count']
            pokemon_record['prev_period_team_percent'] = float(round(top_positive['prev_team_percent'], 2))
            pokemon_record['current_period_team_count'] = top_positive['current_team_count']
            pokemon_record['current_period_team_percent'] = float(round(top_positive['current_team_percent'], 2))
            pokemon_record['usage_change_percent'] = float(round(top_positive['usage_change_percent'], 2))
            response['data']['increased'].append(pokemon_record)

        for top_negative in reversed(top_used[-10:]):
            pokemon_record = Pokemon.query.get(top_negative['pokemon_id']).to_dict()
            pokemon_record['prev_period_team_count'] = top_negative['prev_team_count']
            pokemon_record['prev_period_team_percent'] = float(round(top_negative['prev_team_percent'], 2))
            pokemon_record['current_period_team_count'] = top_negative['current_team_count']
            pokemon_record['current_period_team_percent'] = float(round(top_negative['current_team_percent'], 2))
            pokemon_record['usage_change_percent'] = float(round(top_negative['usage_change_percent'], 2))
            response['data']['decreased'].append(pokemon_record)

        # store response in cache for faster retrieval next time. Cache duration is 35 min, but will be manually
        # invalidated by ingestion method when new data is added
        redis_cache.setex(cache_key, 2100, json.dumps(response))
        logging.info(f"Stored response in cache with key {cache_key}")

        return response
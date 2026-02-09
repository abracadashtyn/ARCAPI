from flask import jsonify, request
from sqlalchemy import ExecutableDDLElement

from app import db
from app.api.PaginationUtils import PaginationUtils
from app.api.v0 import bp
from app.models import Player, PlayerMatch, Match


@bp.route('/players')
def players():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)

        query = Player.query.order_by(Player.name)
        paginated_players = PaginationUtils.paginate_query(query, page, limit)
        return jsonify(paginated_players), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/players/<int:id>')
def player(id):
    try:
        player = Player.query.get_or_404(id)
        response_dict = {
            'id': player.id,
            'name': player.name,
            'match_count': len(player.matches),
            'match_ids': [x.match_id for x in player.matches],
            # TODO add some other calculated fields like most-used pokemon
        }

        return jsonify(response_dict), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/players/<int:id>/matches')
def player_matches(id):
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        paginated_results = db.session.query(PlayerMatch, Match)\
            .join(Match, PlayerMatch.match_id == Match.id)\
            .filter(PlayerMatch.player_id == id)\
            .paginate(page=page, per_page=limit, error_out=False)

        response_json = {
            'success': True,
            'data': [],
            'pagination': {
                'page': page,
                'items_per_page': limit,
                'total_pages': paginated_results.pages,
                'total_items': paginated_results.total
            }
        }
        for playermatch_record, match_record in paginated_results:
            response_json['data'].append({
                'match': {
                    'id': match_record.id,
                    'showdown_id': match_record.showdown_id,
                    'upload_time': match_record.upload_time,
                    'rating': match_record.rating,
                    'private': match_record.private,
                    'format': match_record.format.to_dict(),
                },
                'won_match': playermatch_record.won_match,
                'team': [{
                    'pokemon': x.pokemon.to_dict(),
                    'ability': x.ability.to_dict(),
                    'item': x.item.to_dict(),
                    'moves': [y.to_dict() for y in x.moves]
                } for x in playermatch_record.pokemon]
            })

        return jsonify(response_json), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
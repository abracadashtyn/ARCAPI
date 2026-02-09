from flask import jsonify, request

from app.api.PaginationUtils import PaginationUtils
from app.api.v0 import bp
from app.models import Match, Format


@bp.route('/matches')
def matches():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)

        query = Match.query.order_by(Match.upload_time.desc())
        if 'format_id' in request.args:
            format = request.args.get('format_id', type=int)
            query = query.filter(Match.format_id == format)

        paginated_results = query.paginate(page=page, per_page=limit, error_out=False)

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
        for match_record in paginated_results:
            match_dict = match_record.to_dict()
            match_dict['players'] = []
            for player_match_record in match_record.players:
                match_dict['players'].append({
                    'id': player_match_record.player_id,
                    'won_match': player_match_record.won_match,
                    'name': player_match_record.player.name,
                })
            response_json['data'].append(match_dict)

        return jsonify(response_json), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/matches/<int:id>')
def match(id):
    try:
        match = Match.query.get_or_404(id)
        match_dict = match.to_dict()
        match_dict['players'] = []

        for player_match in match.players:
            match_dict['players'].append({
                'id': player_match.player_id,
                'won_match': player_match.won_match,
                'name': player_match.player.name,
                'team': [{
                    'pokemon': x.pokemon.to_dict(),
                    'ability': x.ability.to_dict(),
                    'item': x.item.to_dict(),
                    'moves': [y.to_dict() for y in x.moves]
                } for x in player_match.pokemon]
            })

        return jsonify(match_dict), 200


    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/formats')
def formats():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        query = Format.query.order_by(Format.name)
        paginated_formats = PaginationUtils.paginate_query(query, page, limit)
        return jsonify(paginated_formats), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
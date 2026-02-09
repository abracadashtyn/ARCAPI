from flask import request
from flask_restx import Namespace, fields, Resource
from sqlalchemy.exc import SQLAlchemyError

from app.api.PaginationUtils import PaginationUtils
from app.api.v0 import api, pagination_model, error_response
from app.models import Player

players_ns = Namespace('Players', description='Endpoints related to pokemon showdown player accounts')
api.add_namespace(players_ns, path='/players')

"""Fetches a list of all players"""
player_model = api.model('Player', {
    'id': fields.Integer,
    'name': fields.String
})
player_list_response = api.model('PlayerListResponse', {
    'success': fields.Boolean,
    'data': fields.List(fields.Nested(player_model)),
    'pagination': fields.Nested(pagination_model)
})
@players_ns.route('/')
class PlayerList(Resource):
    @players_ns.doc('list_players')
    @players_ns.param('page', 'Page number', type='integer', default=1)
    @players_ns.param('limit', 'Items per page', type='integer', default=50)
    @players_ns.param(name='name', description='username (full or partial) to filter results by', type='string')
    @players_ns.response(500, 'Internal server error', error_response)
    @players_ns.marshal_with(player_list_response, code=200)
    def get(self):
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        query = Player.query.order_by(Player.name)
        if 'name' in request.args:
            search_string = request.args['name']
            if '%' not in search_string:
                search_string = f"%{search_string}%"
            query = query.filter(Player.name.like(search_string))
        try:
            return PaginationUtils.paginate_query(query, page, limit)
        except SQLAlchemyError as e:
            api.abort(500, f'Error querying database for formats: {e}')
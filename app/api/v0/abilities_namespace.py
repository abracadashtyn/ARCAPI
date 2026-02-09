from flask import request
from flask_restx import Namespace, fields, Resource
from sqlalchemy.exc import SQLAlchemyError

from app.api.PaginationUtils import PaginationUtils
from app.api.v0 import api, pagination_model, error_response
from app.models import Ability

abilities_ns = Namespace('Abilities', description='Endpoints related to pokemon abilities.')
api.add_namespace(abilities_ns, path='/abilities')


"""Fetches a list of all abilities"""
ability_model = api.model('Ability', {
    'id': fields.Integer,
    'name': fields.String,
})
ability_list_response = api.model('AbilityListResponse', {
    'success': fields.Boolean,
    'data': fields.List(fields.Nested(ability_model)),
    'pagination': fields.Nested(pagination_model)
})
@abilities_ns.route('/')
class AbilityList(Resource):
    @abilities_ns.doc('list_abilities')
    @abilities_ns.param(name='page', description='Page number', type='integer', default=1)
    @abilities_ns.param(name='limit', description='Items per page', type='integer', default=50)
    @abilities_ns.param(name='name', description='Name of ability (full or partial) to filter results by', type='string')
    @abilities_ns.response(500, 'Internal server error', error_response)
    @abilities_ns.marshal_with(ability_list_response, code=200)
    def get(self):
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        query = Ability.query.order_by(Ability.name)
        if 'name' in request.args:
            search_string = request.args['name']
            if '%' not in search_string:
                search_string = f"%{search_string}%"
            query = query.filter(Ability.name.like(search_string))
        try:
            return PaginationUtils.paginate_query(query, page, limit)
        except SQLAlchemyError as e:
            api.abort(500, f'Error querying database for abilities: {e}')


"""Fetches a specific ability by id
ability_detail_response = api.model('AbilityDetailResponse', {
    'success': fields.Boolean,
    'data': fields.List(fields.Nested(ability_model))
})
@abilities_ns.route('/<int:ability_id>')
class AbilityDetail(Resource):
    @abilities_ns.doc('get_ability')
    @abilities_ns.response(404, 'Ability not found', error_response)
    @abilities_ns.response(500, 'Internal server error', error_response)
    @abilities_ns.marshal_with(ability_detail_response, code=200)
    def get(self, ability_id):
        try:
            ability_record = Ability.query.filter_by(id=ability_id).first()
        except SQLAlchemyError as e:
            # Handle database errors specifically
            api.abort(500, f'Error querying database for ability with ID {ability_id}: {e}')

        if not ability_record:
            api.abort(404, f'Ability with ID {ability_id} not found')

        response = {
            'success': True,
            'data': ability_record.to_dict()
        }
        return response"""

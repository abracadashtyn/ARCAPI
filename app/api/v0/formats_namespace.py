from flask import request
from flask_restx import Namespace, fields, Resource
from sqlalchemy.exc import SQLAlchemyError

from app.api.PaginationUtils import PaginationUtils
from app.api.v0 import api, pagination_model, error_response
from app.models import Format

format_ns = Namespace('Formats', description='Endpoints related to game format, as specified by showdown API.')
api.add_namespace(format_ns, path='/formats')

"""Fetches a list of all formats"""
format_model = api.model('Format', {
    'id': fields.Integer,
    'name': fields.String,
    'formatted_name': fields.String,
})
format_list_response = api.model('FormatListResponse', {
    'success': fields.Boolean,
    'data': fields.List(fields.Nested(format_model)),
    'pagination': fields.Nested(pagination_model)
})
@format_ns.route('/')
class FormatList(Resource):
    @format_ns.doc('list_formats')
    @format_ns.param('page', 'Page number', type='integer', default=1)
    @format_ns.param('limit', 'Items per page', type='integer', default=50)
    @format_ns.response(500, 'Internal server error', error_response)
    @format_ns.marshal_with(format_list_response, code=200)
    def get(self):
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        query = Format.query.order_by(Format.name)
        try:
            return PaginationUtils.paginate_query(query, page, limit)
        except SQLAlchemyError as e:
            api.abort(500, f'Error querying database for formats: {e}')
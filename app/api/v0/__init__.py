import json

from flask import Blueprint, request, current_app
from flask_restx import Api, fields


bp = Blueprint('api_v0', __name__, url_prefix='/api/v0')
api_v0 = Api(
    bp,
    version='0.1',
    title='ReplayGenie API',
    doc='/docs'
)

error_response = api_v0.model('ErrorResponse', {
    'success': fields.Boolean(description='Always false for errors', default=False),
    'error': fields.String(description='Error message', required=True)
})

# Global handler for unexpected errors that don't have their own handler defined
@api_v0.errorhandler(Exception)
def handle_error(error):
    return {'success': False, 'error': 'Internal server error'}, 500

@bp.after_request
def add_deprecation_header(response):
    if request.path.startswith("/api/v0/"):
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "Fri, 01 May 2026 00:00:00 GMT"
        response.headers["Link"] = f'<{current_app.config.get('BASE_URL')}/api/v1/>; rel="successor-version"'

        if response.content_type == "application/json":
            data = response.get_json()
            if isinstance(data, dict):
                data["_deprecated"] = ("/api/v0 is deprecated. Please migrate to /api/v1/. This version will be removed "
                                       "in a future release.")
                response.data = json.dumps(data)
    return response

from app.api.v0 import abilities_namespace, config_namespace, formats_namespace, items_namespace, matches_namespace,\
                        moves_namespace, players_namespace, pokemon_namespace, sets_namespace, types_namespace

from flask import Blueprint

bp = Blueprint('tasks', __name__, cli_group=None)

from app.tasks import match_ingestion_tasks, scrape_pokemon_data, database_operations, cache_operations

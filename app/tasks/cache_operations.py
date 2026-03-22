import logging

from app import redis_cache
from app.tasks import bp


@bp.cli.group()
def cacheops():
    pass

@cacheops.command('clear-pokemon')
def clear_pokemon():
    keys = redis_cache.keys(f"pokemon_stats:*:*")
    if keys:
        redis_cache.delete(*keys)
        logging.info(f"Cleared {len(keys)} cached entries")


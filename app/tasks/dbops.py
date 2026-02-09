from sqlalchemy import delete

from app import db
from app.tasks import bp
from app.models import PlayerMatchPokemon, PlayerMatch, Match, pmp_move, PokemonType


@bp.cli.group()
def dbops():
    pass

@dbops.command('populate-types')
def populate_types():
    types = ['Bug', 'Dark', 'Dragon', 'Electric', 'Fairy', 'Fighting', 'Fire', 'Flying', 'Ghost', 'Grass', 'Ground',
             'Ice', 'Normal', 'Poison', 'Psychic', 'Rock', 'Steel', 'Stellar', 'Water']
    for type in types:
        if PokemonType.query.filter(PokemonType.name == type).first() is None:
            db.session.add(PokemonType(name=type))
    db.session.commit()

@dbops.command('clear-matches')
def clear_matches():
    db.session.execute(delete(pmp_move))
    PlayerMatchPokemon.query.delete()
    PlayerMatch.query.delete()
    Match.query.delete()
    db.session.commit()

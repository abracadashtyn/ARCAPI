import logging

import click
from sqlalchemy import delete

from app import db
from app.tasks import bp
from app.models import PlayerMatchPokemon, PlayerMatch, Match, pmp_move, PokemonType
from app.tasks.showdown_match_parser import ShowdownMatchParser


@bp.cli.group()
def dbops():
    pass

@dbops.command('clear-matches')
def clear_matches():
    db.session.execute(delete(pmp_move))
    PlayerMatchPokemon.query.delete()
    PlayerMatch.query.delete()
    Match.query.delete()
    db.session.commit()


@dbops.command('migrate-moves')
def migrate_moves():
    logging.basicConfig(level=logging.INFO)
    batch_size = 1000
    offset = 0
    reprocess = []

    while True:
        batch = PlayerMatchPokemon.query.limit(batch_size).offset(offset).all()
        if not batch:
            break

        for pmp in batch:
            moves = db.session.query(pmp_move.c.move_id).filter(pmp_move.c.pmp_id == pmp.id).order_by(pmp_move.c.move_id).all()

            if len(moves) > 4:
                logging.error(f"Too many moves for {pmp.id}")
                continue

            elif len(moves) < 4:
                match_id = PlayerMatch.query.get(pmp.player_match_id).match_id
                reprocess.append(match_id)
                logging.error(
                    f"Only found {len(moves)} moves for {pmp.id}, match id {match_id}")
                continue

            pmp.move_1_id = moves[0][0] if len(moves) > 0 else None
            pmp.move_2_id = moves[1][0] if len(moves) > 1 else None
            pmp.move_3_id = moves[2][0] if len(moves) > 2 else None
            pmp.move_4_id = moves[3][0] if len(moves) > 3 else None

        db.session.commit()
        db.session.expunge_all()
        offset += batch_size
        logging.info(f"Processed {offset} records...\nREPROCESS: {reprocess}")
        reprocess = []



@dbops.command('reprocess-matches')
@click.option('--ids', '-i', help='Comma-separated list of IDs')
@click.option('--wait', '-w', is_flag=True, default=True,
              help='whether to wait REQUEST_DELAY seconds before calling showdown API (to not hammer it or get rate limited)')
def reprocess_matches(ids, wait):
    logging.basicConfig(level=logging.INFO)
    if ids:
        id_list = [int(x.strip()) for x in ids.split(',')]

    for id in id_list:
        match = Match.query.get(id)
        if match:
            logging.info(f"Processing match with id {match.id}, '{match.format.name}-{match.showdown_id}'")
            match_parser = ShowdownMatchParser(match, wait)
            match_parser.parse_log_details()
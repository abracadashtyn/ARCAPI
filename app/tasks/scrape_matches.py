import json
import logging
import os

import click
import requests
from app.tasks.match_log_parser import MatchLogParser

from app.tasks import bp
from app.models import Format, Match, PlayerMatch
from app import db


@bp.cli.group()
def showdown():
    """Commands to scrape matches from showdown urls"""
    pass

@showdown.command('scrape-new')
@click.option('--localmode', '-l', 'local_mode', is_flag=True, default=False,
              help='if true, pulls from showdown data in static test data files, and fails if file does not exist.')
def scrape_new(local_mode):
    # TODO: set this as a config parameter or something
    game_format = "gen9vgc2026regfbo3"
    game_format_record = Format.get_or_create(game_format)
    if local_mode:
        # load from local data for testing purposes
        with open(os.path.join(os.getcwd(), 'app', 'static', 'test_data', 'search.json'), 'r', encoding='utf-8') as f:
            matches_json = json.load(f)
    else:
        # query showdown api for all matches in desired format.
        list_replays_url = "https://replay.pokemonshowdown.com/search.json"
        params = {"format": game_format_record.name}
        response = requests.get(list_replays_url, params=params)
        if response.status_code != 200:
            logging.error(f"Something went wrong with web request: {response}")
            exit(1)
        else:
            matches_json = response.json()

    for match_json in matches_json:
        # parse out numeric id for match
        id_strings = match_json['id'].split("-")
        if len(id_strings) != 2:
            logging.error(f"No parser implemented for match id with format {match_json['id']}")
            exit(100)
        try:
            showdown_id = int(id_strings[1])
        except ValueError:
            logging.error(f"Match ID {id_strings[1]} is not numeric; unsure how to handle. ")
            exit(101)

        try:
            # check to see if a record for this match already exists
            match_record = Match.query.filter_by(showdown_id=showdown_id).first()
            if match_record is None:
                print(f"Match record with showdown id {showdown_id} does not exist! Creating now.")
                match_record = Match()
                match_record.showdown_id = showdown_id
                match_record.upload_time = match_json["uploadtime"]
                match_record.rating = match_json["rating"]
                match_record.private = match_json["private"]
                match_record.format = game_format_record
                db.session.add(match_record)
                db.session.commit()
                print(f"Created new record for match with id {match_record.id}")
            else:
                print(f"Record for match with showdown id {showdown_id} already exists with id {match_record.id}")
                # TODO exit or continue once testing is done; already processed match should not re-process

            # initialize a log parser to fetch and process the log of the game in question
            log_parser = MatchLogParser(game_format, showdown_id, local_mode)
            match_record.position_in_set = log_parser.get_sequence_in_set()

            player1_record, player2_record = log_parser.get_players()

            # determine who won the match and create a PlayerMatch record for each player
            player_1_match_record = PlayerMatch.get_or_create(player1_record.id, match_record.id)
            player_2_match_record = PlayerMatch.get_or_create(player2_record.id, match_record.id)
            winner = log_parser.get_winner_name()
            if winner == player1_record.name:
                player_1_match_record.won_match = True
                player_2_match_record.won_match = False
            elif winner == player2_record.name:
                player_1_match_record.won_match = False
                player_2_match_record.won_match = True
            else:
                raise Exception(f"Winner of match {winner} does not match either player name ({player1_record.name} or "
                              f"{player2_record.name})")
            db.session.commit()

            # parse pokemon
            log_parser.get_pokemon_by_player(player_1_match_record.id, player_2_match_record.id)
        except Exception as e:
            print(f"Something went wrong parsing record {showdown_id}: {e}")

        print("=============================")


    exit(1)






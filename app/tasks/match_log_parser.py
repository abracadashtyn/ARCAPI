import logging
import os
import re

import requests

from app import db
from app.models import Player, Pokemon, PokemonType, PlayerMatchPokemon, Item, Ability, Move


class MatchLogParser:
    def __init__(self, game_format_name, showdown_id):
        replay_log_url = f"https://replay.pokemonshowdown.com/{game_format_name}-{showdown_id}.log"
        replay_log_response = requests.get(replay_log_url)
        if replay_log_response.status_code != 200:
            logging.error(f"Something went wrong with web request: {replay_log_url}")
            raise Exception(f"Something went wrong with web request: {replay_log_url}")
        log_string = replay_log_response.text
        '''with open(os.path.join(os.getcwd(), 'app', 'tasks', 'test_data', f"{game_format_name}-{showdown_id}.txt"), 'r',
                  encoding='utf-8') as f:
            log_string = f.read()'''

        self.log_lines = log_string.splitlines()

    def clean_and_split_line(self, line):
        return line.lstrip('|').rstrip('|').split('|')

    def get_sequence_in_set(self):
        bestof_line = None
        for line in self.log_lines:
            if 'bestof' in line:
                bestof_line = line
                break
        game_number = re.search("Game ([0-9])", bestof_line)
        if not game_number or game_number.group(1) == "":
            logging.error(f"Not able to parse game number from '{bestof_line}'")
            return None
        else:
            return int(game_number.group(1))


    def get_players(self):
        player1_record, player2_record = None, None
        players = [x for x in self.log_lines if x.startswith("|player|")]
        if len(players) > 2:
            players = players[:2]
        elif len(players) < 2:
            raise Exception(f"Did not find enough lines defining players in match; not sure how to parse\n{players}")

        for player_info in players:
            player_info_chunks = self.clean_and_split_line(player_info)
            if player_info_chunks[1].lower() == "p1":
                player1_record = Player.get_or_create(player_info_chunks[2])
            elif player_info_chunks[1].lower() == "p2":
                player2_record = Player.get_or_create(player_info_chunks[2])
            else:
                raise Exception(f"Was not able to parse player position for line {player_info}")

        # ensure record for both players were populated from the above logic
        if player1_record is None or player2_record is None:
            raise Exception(f"Could not parse player positions from log info {players}")

        return player1_record, player2_record

    def get_winner_name(self):
        winner_lines = [x for x in self.log_lines if x.startswith('|win|')]
        if len(winner_lines) > 1:
            raise Exception(f"Found too many lines ({len(winner_lines)}) defining winner: {winner_lines}")
        elif len(winner_lines) < 1:
            raise Exception(f"Could not find any lines with info on winner; please check data and try again. ")

        winner = self.clean_and_split_line(winner_lines[0])
        return winner[1]

    def get_pokemon_by_player(self, p1_match_record_id, p2_match_record_id):
        teams = [x for x in self.log_lines if x.startswith("|showteam|")]
        if len(teams) != 2:
            raise Exception(f"There should be two 'showteam' records, one for each player, but , but {len(teams)} were "
                          f"found in the log data.")

        for team in teams:
            team_info = re.search('\|showteam\|(p[1,2])\|(.*?)](.*?)](.*?)](.*?)](.*?)](.*)', team)
            if team_info.group(1) == 'p1':
                pm_record_id = p1_match_record_id
            elif team_info.group(1) == 'p2':
                pm_record_id = p2_match_record_id
            else:
                raise Exception(f"Not able to determine which player team record belongs to. Please check data format.")

            for i in range(2, 8):
                pkmn_info = [x for x in team_info.group(i).split('|')]

                # first field is the name
                pokemon_record = Pokemon.query.filter_by(name=pkmn_info[0]).first()

                # if this is a new pokemon record, we also need to add its types from the last field in the log.
                # in theory we should never hit this
                if pokemon_record is None:
                    pokemon_record = Pokemon(name=pkmn_info[0])
                    print("THIS IS A PREVIOUSLY UNSEEN POKEMON!! check if this works ")
                    db.session.add(pokemon_record)
                    db.session.commit()
                    types = [x for x in pkmn_info[-1].split(',') if x != ""]
                    for type in types:
                        pokemon_record.types.append(PokemonType.get_or_create(type))
                    db.session.commit()

                pmp_record = PlayerMatchPokemon.get_or_create(pm_record_id, pokemon_record.id)

                #second field is blank in all the test data I saw - might eventually be tera type? for now adding exit to manually validate data
                if pkmn_info[1] != "":
                    raise Exception(f"Found value {pkmn_info[1]} in line {team_info.group(i)} - not sure how to handle")


                # third field is the item the pokemon is holding
                if pkmn_info[2] != "":
                    pmp_record.item = Item.get_or_create(pkmn_info[2])

                # third field is ability
                if pkmn_info[3] != "":
                    pmp_record.ability = Ability.get_or_create(pkmn_info[3])

                # fourth field is moveset
                if pkmn_info[4] != "":
                    moves = pkmn_info[4].split(',')
                    for move in moves:
                        move_record = Move.get_or_create(move)
                        if move_record not in pmp_record.moves:
                            pmp_record.moves.append(move_record)

                db.session.commit()

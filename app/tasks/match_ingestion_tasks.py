import datetime
import json
import os
import time
import traceback
import urllib
from enum import Enum

import click
import requests
from flask import current_app
from sqlalchemy import literal_column, update, exists
from sqlalchemy.orm import aliased
from app import db
from app.exceptions import AlreadyExistsException, CustomGameException
from app.models import Format, Match, PlayerMatch, Player, PlayerMatchPokemon
from app.tasks import bp
from app.tasks.cache_operations import warm
from app.tasks.showdown_match_parser import ShowdownMatchParser

list_replays_url = "https://replay.pokemonshowdown.com/search.json"


@bp.cli.group()
def showdown():
    """Commands to scrape matches from showdown urls"""
    pass


class Mode(Enum):
    new = 'new'
    backfill = 'backfill'

class SeenMatchBehavior(Enum):
    skip = 'skip'
    reprocess = 'reprocess'
    exit = 'e'

@showdown.command('scrape')
@click.pass_context
@click.option('--format_id', '-f', type=int)
@click.option('--mode', '-m', type=click.Choice(Mode), default=Mode.new,
              help="Default is 'new', which will ingest matches that are newer than the most recent match of the given "
                   "format in the db. If there are no matches in the database, it will return. 'backfill' will ingest "
                   "matches, working backwards from either 'backfill_start' if present, the oldest record for this "
                   "format in the database if any records are present, and the current time if the matches table is empty.")
@click.option('--backfill_start', '-bs', type=int, help="This parameter is only used when the mode is backfill. "
                                              "If provided, the backfill ingestion will start at this point in time.")
@click.option('--backfill_end', '-be', type=int, help="This parameter is only used when the mode is backfill."
                                              "match ingestion will stop once this timestamp is reached.")
@click.option('--seen', '-s', type=click.Choice(SeenMatchBehavior), default=SeenMatchBehavior.exit,
              help="What to do when when the ingestion process encounters a match that already exists in the database. "
                   "'skip' will skip reprocessing matches that already have a record in the matches table, but the "
                   "ingestion process won't be halted. 'reprocess' will run matches that already have a record through"
                   "the match parser again, updating or adding any incomplete data. 'exit' will stop the execution of"
                   "the ingestion process when a match that already has a record is encountered.")
def scrape(ctx, format_id, mode, backfill_start, backfill_end, seen):
    # get the format id - default to current as specified in config if no value is provided
    format_id = current_app.config.get('CURRENT_FORMAT_ID') if format_id is None else format_id
    format = Format.query.get(format_id)
    if format is None:
        click.echo("ERROR: format ID does not exist in database")
        exit(1)

    start_time = None
    end_time = None

    if mode == Mode.new:
        error_file_name = f'scrape-new-{int(time.time())}.json'
        last_match = Match.query.filter_by(format_id=format.id).order_by(Match.upload_time.desc()).first()
        if last_match is None:
            click.echo("The matches table is currently empty. Please use backfill mode.")
            return
        end_time = last_match.upload_time

        if seen is None:
            seen = SeenMatchBehavior.exit

        if backfill_start is not None or backfill_end is not None:
            click.echo(f"Warning: 'backfill_start' and 'backfill_end' parameters are only used in backfill mode. "
                       f"Provided values will be discarded.")

        click.echo(f"Mode is 'new' and seen behavior is '{seen.name}'. The timestamp of the most recent match is "
                   f"{end_time} ({datetime.datetime.fromtimestamp(end_time)}), matches newer "
                   f"than this will be scraped.")


    elif mode == Mode.backfill:
        error_file_name = f'scrape-backfill-{int(time.time())}.json'
        if seen is None:
            seen = SeenMatchBehavior.exit

        if backfill_start is None:
            earliest_match = Match.query.filter_by(format_id=format.id).order_by(Match.upload_time.asc()).first()
            if earliest_match is None:
                start_time = int(datetime.datetime.now().timestamp())
            else:
                start_time = earliest_match.upload_time
        else:
            start_time = backfill_start

        stmnt = f"Mode is 'backfill' and seen behavior is '{seen.name}'. Will look for matches that occur "

        if backfill_end is not None:
            end_time = backfill_end
            stmnt += f"before '{backfill_end}' ({datetime.datetime.fromtimestamp(end_time)}) and "

        stmnt += f"after {start_time} ({datetime.datetime.fromtimestamp(start_time)})"
        click.echo(stmnt)

    else:
        # here as a sanity check, should never be reached.
        click.echo(f"Error: mode '{mode}' has not been implemented.")
        exit(1)

    error_file_path = os.path.join(os.getcwd(), 'app', 'tasks', 'errors', error_file_name)

    # query showdown api for all matches in desired format.
    params = {"format": format.name}
    if mode == Mode.backfill:
        params['before'] = start_time

    response = requests.get(list_replays_url, params=params)
    if response.status_code != 200:
        click.echo(f"ERROR: Something went wrong searching showdown: {response.status_code}: {response.text}")
        exit(3)

    matches_json = response.json()
    matches_added_count = 0
    throw_if_exists = False if seen == SeenMatchBehavior.reprocess else True
    while len(matches_json) > 0:
        for match_json in matches_json:
            if end_time is not None and match_json['uploadtime'] < end_time:
                click.echo(f"Match {match_json['id']} with timestamp {match_json['uploadtime']} is older than end_time"
                             f" {end_time}. Match scraping is complete. Added {matches_added_count} matches "
                             f"to database.")
                # warm cache for format and most commonly used pokemon
                ctx.invoke(warm, format_id=format_id, api_version=current_app.config['CURRENT_API_VERSION'])
                return
            else:
                click.echo(f"Processing match {match_json['id']}")
                match_parser = None
                try:
                    match_parser = ShowdownMatchParser.construct_from_json(match_json, format.id, wait=True, throw_if_exists=throw_if_exists)
                    match_parser.parse_log_details()
                    matches_added_count += 1
                except AlreadyExistsException:
                    if seen == SeenMatchBehavior.skip:
                        click.echo(f"Match {match_json['id']} already exists. Skipping and continuing to next...")
                        continue
                    elif seen == SeenMatchBehavior.exit:
                        click.echo(f"Match {match_json['id']} already exists. Mode is 'exit' so match ingestion is done."
                                   f" Warming cache...")
                        ctx.invoke(warm, format_id=format_id, api_version=current_app.config['CURRENT_API_VERSION'])
                        return
                except CustomGameException:
                    click.echo("This is a custom game. Will delete any data populated by it and skip.")
                    if match_parser:
                        db.session.delete(match_parser.match_record)
                        db.session.commit()
                    continue
                except Exception as e:
                    # any exception thrown beyond AlreadyExistsException is a genuine processing error. log it and continue
                    click.echo(f"ERROR: problem processing match {match_json['id']}: {type(e).__name__}"
                               f" {e.args[0] if e.args else ''}")
                    click.echo(traceback.format_exc())
                    error_json = {
                        "showdown_id": match_json['id'],
                        "error": str(e),
                        "match_json": match_json
                    }
                    with open(error_file_path, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(error_json) + "\n")
                    if match_parser:
                        db.session.delete(match_parser.match_record)
                        db.session.commit()
                    continue

        # 51 is the limit of matches that can be returned by this call, so if there are 51, there might be more results
        # on the next page. Query for those.
        if len(matches_json) == 51:
            params["before"] = matches_json[-1]['uploadtime']
            click.echo(
                f"Processed all results from this page, getting more matches before timestamp {params['before']}")
            response = requests.get(list_replays_url, params=params)
            if response.status_code != 200:
                click.echo(f"ERROR: Something went wrong with web request: {response}")
                exit(1)
            else:
                matches_json = response.json()
        else:
            click.echo(f"There were {len(matches_json)} matches in these results, so we've seen everything")
            matches_json = []

    # warm cache for format and most commonly used pokemon
    click.echo(f"Now warming cache for format.")
    ctx.invoke(warm, format_id=format_id, api_version=current_app.config['CURRENT_API_VERSION'])


@showdown.command('assign-set')
@click.option('--format_id', '-f', type=int)
def assign_set_id(format_id):
    if format_id is None:
        format_id = current_app.config['CURRENT_API_VERSION']

    format = Format.query.get(format_id)
    if not format:
        click.echo(f"Error: could not find format with id {format_id}")
        exit(1)
    if format.has_series is False:
        click.echo(f"Format {format.name} (id: {format.id}) does not have sets so no ids will be assigned.")
        return

    set_id = db.session.query(Match.set_id).order_by(Match.set_id.desc()).first()
    set_id = set_id[0] + 1 if set_id[0] is not None else 0
    click.echo(f"Assigning sets to matches of format_id {format_id}. Will start incrementing set ids from {set_id}")
    batch_size = 100
    offset = 0

    pm1 = aliased(PlayerMatch)
    pm2 = aliased(PlayerMatch)
    p1 = aliased(Player)
    p2 = aliased(Player)
    m1 = aliased(Match)

    while True:
        batch_query = db.session\
            .query(
                pm1.player_id.label("p1_id"),
                p1.name.label('p1_name'),
                pm2.player_id.label("p2_id"),
                p2.name.label('p2_name'),
                literal_column("GROUP_CONCAT(matches.position_in_set, '|', matches.id, '|', matches.showdown_id ORDER BY matches.showdown_id SEPARATOR ',')").label('match_list'),
                Match.format_id.label('format')
            ).join(p1, pm1.player_id == p1.id)\
            .join(pm2, pm1.match_id == pm2.match_id)\
            .join(p2, pm2.player_id == p2.id)\
            .join(Match, pm1.match_id == Match.id)\
            .filter(
                Match.set_id.is_(None),
                Match.position_in_set.is_not(None),
                pm1.player_id < pm2.player_id,
                Match.format_id == format_id
            ).group_by(
                pm1.player_id,
                p1.name,
                pm2.player_id,
                p2.name,
                Match.format_id
            ).limit(batch_size)

        #click.echo(f'Will update set id with statement {batch_query.statement.compile(compile_kwargs={"literal_binds": True})}')
        batch = batch_query.all()

        if not batch:
            click.echo(f"Did not find any matches without set_id to process. exiting.")
            break

        for result in batch:
            click.echo('-------------------')
            click.echo(f"Parsing record {result}")

            all_match_data = []
            for m in result[4].split(','):
                m = m.split("|")
                all_match_data.append({
                    'position': int(m[0]),
                    'id': int(m[1]),
                    'showdown_id': m[2],
                    'pokemon': None
                })

            # get all pokemon used by match:
            pokemon_data_base_query = db.session.query(
                PlayerMatch.match_id,
                literal_column("GROUP_CONCAT(pm_pokemon.pokemon_id ORDER BY pm_pokemon.pokemon_id SEPARATOR ',')").label('poke_list'),
            ).select_from(
                PlayerMatch
            ).join(
                PlayerMatchPokemon, PlayerMatch.id == PlayerMatchPokemon.player_match_id
            ).group_by(
                PlayerMatch.match_id
            )

            pokemon_data = pokemon_data_base_query.filter(
                PlayerMatch.match_id.in_([x['id'] for x in all_match_data])
            ).all()
            poke_match_map = {int(x[0]): x[1] for x in pokemon_data}

            click.echo(f"match to pokemon map {poke_match_map}")

            # loop through all the matches and group them into sets.
            match_sets = []
            match_set = {1: None, 2: None, 3: None}
            previous = 0
            for match in all_match_data:
                # assign the pokemon to the match for comparison
                if match['id'] not in poke_match_map.keys():
                    click.echo(f"ERROR: Could not locate pokemon for match with id {match['id']}")
                    exit(9)
                match['pokemon'] = poke_match_map[match['id']]

                click.echo(f"Processing match {match}")

                #if the current match position is lower than the previous or is already filled in this set, then we've
                # looped around to a new set. Add the previous set to the list and start populating a new one
                if match['position'] <= previous or match_set[match['position']] is not None:
                    click.echo(f"Match {match['id']} position {match['position']} is less than previous position {previous}; adding new set.")
                    match_sets.append(match_set)
                    match_set = {1: None, 2: None, 3: None}

                # check to make sure the pokemon match any previous matches in the set. If not, it's a new set.
                elif match['position'] > 1 and previous != 0 and match['pokemon'] != match_set[previous]['pokemon']:
                    click.echo(f'match {match['id']} at position {match['position']} has different pokemon than previous\n'
                          f'({match['pokemon']} versus {match_set[previous]['pokemon']})\n'
                          f'creating new set.')
                    match_sets.append(match_set)
                    match_set = {1: None, 2: None, 3: None}

                match_set[match['position']] = match
                previous = match['position']

            match_sets.append(match_set)
            click.echo(f'found {len(match_sets)} match sets')

            # assign a set id to each defined set of matches
            for match_index, match_set in enumerate(match_sets):
                # if the first set of matches is missing it's first match, this might be part of an existing series
                # that was already catalogued in the database earlier. If so, we will search for the match immediately
                # preceding the first present in this set and determine if they're a match by the pokemon used in them.
                # if so, give all items in this match set the same set id as the existing series.
                if match_index == 0 and match_set[1] is None:
                    click.echo(f"\tFirst match in set {match_index} is missing; will query for existing set to append to")
                    earliest_position = 2 if match_set[2] else 3
                    showdown_id = match_set[earliest_position]['showdown_id']

                    prev_set = db.session \
                        .query(
                            Match.id,
                            Match.set_id,
                            Match.position_in_set,
                            Match.upload_time
                        ).join(pm1, pm1.match_id == Match.id)\
                        .join(p1, pm1.player_id == p1.id) \
                        .join(pm2, pm2.match_id == Match.id) \
                        .join(p2, pm2.player_id == p2.id) \
                        .filter(
                            Match.set_id.is_not(None),
                            Match.showdown_id < showdown_id,
                            Match.position_in_set < earliest_position,
                            pm1.player_id < pm2.player_id,
                            pm1.player_id == result[0],
                            pm2.player_id == result[2],
                            ~exists().where(
                                m1.set_id == Match.set_id,
                                m1.position_in_set == earliest_position
                            )
                        ).order_by(Match.showdown_id.desc())\
                        .first()

                    if prev_set is not None:
                        click.echo(f'Found possible previous set with id {prev_set[0]}; checking pokemon to verify')
                        prev_match_pokemon = pokemon_data_base_query.filter(PlayerMatch.match_id == prev_set[0]).first()
                        click.echo(f'prev_match_pokemon: {prev_match_pokemon}')

                        if all([True if x['pokemon'] == prev_match_pokemon[1] else False for x in match_set.values() if x is not None]):
                            click.echo(f"Also matched previous pokemon!")
                            click.echo(f"Appending this match to existing set with set_id {prev_set.set_id}")
                            stmt = update(Match).where(Match.id.in_([x['id'] for x in match_set.values() if x is not None])).values(set_id=prev_set.set_id)
                            db.session.execute(stmt)
                            continue
                    else:
                        click.echo("No existing set found to match this record. Will create new set id for it.")

                set_match_ids = [x['id'] for x in match_set.values() if x is not None]
                click.echo(f"Assigning match ids {set_match_ids} to set id {set_id}")
                stmt = update(Match).where(Match.id.in_(set_match_ids)).values(set_id=set_id)
                #click.echo(f'Will update set id with statement {stmt.compile(compile_kwargs={"literal_binds": True})}')
                db.session.execute(stmt)
                set_id += 1

            db.session.commit()

        db.session.commit()
        db.session.expunge_all()
        offset += batch_size
        click.echo('fetching next batch of match records.')

    click.echo(f"Finished assigning set_ids")

@showdown.command('rerun-failed')
def rerun_failed():
    formats = Format.query.all()
    formats_dict = {f.name: f.id for f in formats}

    error_files_dir = os.path.join(os.getcwd(), 'app', 'tasks', 'errors')
    error_files = []
    with os.scandir(error_files_dir) as dir_contents:
        error_files = [entry.name for entry in dir_contents if entry.is_file()]

    for error_file in error_files:
        click.echo(f"---------------------\nerror file name: {error_file}")
        json_entries = []
        jobs_failed_again = []
        with open(os.path.join(error_files_dir, error_file), 'r') as f:
            json_entries = [json.loads(x) for x in f]
        for json_entry in json_entries:
            click.echo(f"Processing match {json_entry['showdown_id']}\nOriginal error: '{json_entry['error']}'")
            match_parser = None
            try:
                id_strings = ShowdownMatchParser.parse_id_string(json_entry['showdown_id'])
                format_id = formats_dict[id_strings['format_name']]
                match_parser = ShowdownMatchParser.construct_from_json(json_entry['match_json'], format_id, wait=True,
                                                                       throw_if_exists=True)
                match_parser.parse_log_details()
                click.echo("Successfully reran job!")
            except AlreadyExistsException:
                click.echo(f"Match {json_entry['showdown_id']} already exists, skipping.")
                continue
            except CustomGameException:
                click.echo("This is a custom game. Will delete any data populated by it and skip.")
                if match_parser:
                    db.session.delete(match_parser.match_record)
                    db.session.commit()
                continue
            except Exception as e:
                error_string = f"{type(e).__name__}: {e.args[0] if e.args else ''}"
                click.echo(f"ERROR: problem processing match {json_entry['showdown_id']}: {error_string}")
                click.echo(traceback.format_exc())
                jobs_failed_again.append({
                    "showdown_id": json_entry['showdown_id'],
                    "error": error_string,
                    "failed_already": True,
                    "prev_failure_reason": json_entry['error'],
                    "match_json": json_entry['match_json']
                })
                if match_parser:
                    db.session.delete(match_parser.match_record)
                    db.session.commit()
                continue

        if len(jobs_failed_again) > 0:
            click.echo(f"{len(jobs_failed_again)} jobs failed again.")
            with open(os.path.join(error_files_dir, error_file), 'w', encoding='utf-8') as f:
                for j in jobs_failed_again:
                    f.write(json.dumps(j) + '\n')
        else:
            click.echo(f"All jobs successfully reran! Deleting error file.")
            os.remove(os.path.join(error_files_dir, error_file))


@showdown.command('scrape-one')
@click.pass_context
@click.option('--showdown_id', '-i', type=str, help='the showdown id consisting of <format>-<match_identifier>')
def scrape_one(ctx, showdown_id):
    base_url = "https://replay.pokemonshowdown.com/"
    request_url = urllib.parse.urljoin(base_url, f'{showdown_id}.json')
    click.echo(f"Requesting from '{request_url}'")
    response = requests.get(request_url)

    if not response.ok:
        click.echo(f"Something went wrong requesting match data from showdown: ERROR {response.status_code} "
                   f"{response.reason} {response.text}")
        exit(1)

    match_json = response.json()
    try:
        match_format = Format.query.filter(Format.name == match_json['formatid']).one_or_none()
    except KeyError:
        click.echo(f"could not find format in match_json response {match_json}")
        exit(1)

    click.echo(f"Processing match {match_json['id']}")
    match_parser = ShowdownMatchParser.construct_from_json(match_json, match_format.id, wait=True, throw_if_exists=False)
    match_parser.parse_log_details()

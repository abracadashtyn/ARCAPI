import json
import logging
import os

import requests
from bs4 import BeautifulSoup

from app import db
from app.tasks import bp
from app.models import Pokemon, PokemonType, Ability


@bp.cli.group()
def pokedex():
    """Commands to scrape pokemon information from various sources"""
    pass


@pokedex.command('scrape-serebii')
def scrape_serebii():
    url_to_scrape = "https://www.serebii.net/pokemon/nationalpokedex.shtml"
    response = requests.get(url_to_scrape)
    if response.status_code != 200:
        logging.error(f"Error scraping {url_to_scrape}: {response}")
        raise Exception("Failed to scrape serebii.")
    page_soup = BeautifulSoup(response.text, "html.parser")

    #optionally, write to file for testing purposes
    '''with open(os.path.join(os.getcwd(), 'app', 'tasks', 'test_data', 'serebii_pokedex.html'), 'w+', encoding='utf-8') as f:
        f.write(page_soup.prettify())'''
    #open saved file from above, for testing purposes
    '''with open(os.path.join(os.getcwd(), 'app', 'tasks', 'test_data', 'serebii_pokedex.html'), 'r', encoding='utf-8') as f:
        page_soup = BeautifulSoup(f.read(), "html.parser")'''

    dex_table = page_soup.find('table', attrs={'class': 'dextable'})
    if dex_table is None:
        logging.error(f"Could not find dextable in page. Please check format of table and try again.")
        raise Exception("Failed to scrape serebii.")

    rows = dex_table.find_all('tr')
    for row in rows:
        tds = row.find_all('td', attrs={'class': 'fooinfo'})
        if tds is not None and len(tds) > 0:
            pkmn_id = tds[0].get_text(strip=True)
            pkmn_id = int(pkmn_id.lstrip("#"))
            pkmn_name = tds[2].get_text(strip=True)
            pkmn_record = Pokemon.get_or_create(pkmn_name, pkmn_id)
            for type in tds[3].find_all('a'):
                type_name = type.get('href').split('/')[-1]
                type_record = PokemonType.get_or_create(type_name.capitalize())
                if type_record not in pkmn_record.types:
                    pkmn_record.types.append(type_record)
            logging.info(f"Added record for #{pkmn_id} {pkmn_name}")
            db.session.commit()


@pokedex.command('scrape-showdown')
def scrape_showdown_pokedex():
    '''query_url = 'https://play.pokemonshowdown.com/data/pokedex.json'
    response = requests.get(query_url)
    if response.status_code != 200:
        logging.error(f"Error scraping {query_url}: {response}")
        raise Exception("Failed to scrape showdown.")
    poke_data = response.json()

    #optionally, write to file for testing purposes
    with open(os.path.join(os.getcwd(), 'app', 'tasks', 'test_data', 'showdown-pokedex.json'), 'w+', encoding='utf-8') as f:
        f.write(json.dumps(poke_data, indent=4))'''

    #open saved file from above, for testing purposes
    with open(os.path.join(os.getcwd(), 'app', 'tasks', 'test_data', 'showdown-pokedex.json'), 'r', encoding='utf-8') as f:
        poke_data = json.loads(f.read())

    for pokemon in poke_data.values():
        # cosmetic form pokemon will not have a dex number associated; skip them right away
        if 'isCosmeticForme' in pokemon and (pokemon['isCosmeticForme'] is True or pokemon['isCosmeticForme'].lower() == 'true'):
            print(f"{pokemon['name']} is cosmetic in nature; will not create record.")
            continue

        print(f"Parsing pokemon #{pokemon['num']} {pokemon['name']}")
        # remove player-created pokemon that don't have real dex numbers
        if pokemon['num'] < 0:
            print("This pokemon is not real; will not create record.")
            continue

        poke_record = Pokemon.get_or_create(pokemon['name'], pokemon['num'])

        if 'tier' in pokemon:
            poke_record.tier = pokemon['tier']
        if 'isNonstandard' in pokemon:
            poke_record.is_nonstandard = pokemon['isNonstandard']

        # if this pokemon is a subform of another pokemon, set the base_form column
        if 'baseSpecies' in pokemon and pokemon['baseSpecies'] != pokemon['name']:
            poke_record.base_species = Pokemon.get_or_create(pokemon['baseSpecies'], pokemon['num'])

        # associate any types, adding records if needed
        if 'types' in pokemon:
            for type in pokemon['types']:
                poke_type = PokemonType.get_or_create(type)
                if poke_type not in poke_record.types:
                    poke_record.types.append(poke_type)

        # add any abilities found on the entry, but don't associate with pokemon until match time
        if 'abilities' in pokemon:
            for x, ability in pokemon['abilities'].items():
                Ability.get_or_create(ability)

        db.session.commit()











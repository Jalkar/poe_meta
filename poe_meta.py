import argparse
import logging
import json
import requests
import atexit
import csv
import os
import time

from poe_account import Account
from poe_character import Character

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    handlers=[logging.FileHandler("poe_meta.log"), logging.StreamHandler()],
                    level=logging.DEBUG,
                    datefmt='%Y-%m-%d %H:%M:%S')
LOGGER = logging.getLogger()

PATH_TO_CHARACTER_CHECKPOINT = "character_checkpoint.csv"
PATH_TO_CHANGE_ID_CHECKPOINT = "change_id_checkpoint.csv"


class poe_meta:
    def __init__(self):
        self._change_id = ""
        self._accounts = dict()
        self._trade_api_call = 0

    @property
    def change_id(self):
        """The change_id property."""
        return self._change_id

    @change_id.setter
    def change_id(self, value):
        self._change_id = value

    @property
    def accounts(self):
        """The accounts property."""
        return self._accounts

    @accounts.setter
    def accounts(self, value):
        self._accounts = value

    @property
    def trade_api_call(self):
        """The trade_api_call property."""
        return self._trade_api_call

    @trade_api_call.setter
    def trade_api_call(self, value):
        self._trade_api_call = value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s", "--sessionid",
        type=str,
        help="provide the sessionId for poe website connectivity")

    parser.add_argument(
        "-c", "--changeid",
        type=str,
        help="next change id for the poe trade api - WARNING WILL BE OVERRIDING THE FILE CHECKPOINT")

    args = parser.parse_args()
    meta = poe_meta()
    load_accounts(meta)
    if args.changeid:
        meta.change_id = args.changeid
    atexit.register(save_accounts, meta)
    while True:
        request_trade_api(meta)
        request_passives_and_items(meta)

# "https://www.pathofexile.com/character-window/get-passive-skills?accountName="..accountName.."&character="..charData.name.."&realm=pc
# "https://www.pathofexile.com/character-window/get-items?accountName="..accountName.."&character="..charData.name.."&realm=pc


def request_passives_and_items(meta):
    for key_account, account in meta.accounts.items():
        if not account.extracted:
            for character in account.characters:
                uri_passives = "https://www.pathofexile.com/character-window/get-passive-skills?accountName={0}&character={1}&realm=pc"
                uri_items = "https://www.pathofexile.com/character-window/get-items?accountName={0}&character={1}&realm=pc"
                passive = request_get_windows(uri_passives.format(account.account_name, character.name))
                items = request_get_windows(uri_items.format(account.account_name, character.name))
                if passive and items:
                    item_from_passive = passive.get('items', "")
                    items_from_items = items.get('items', "")
                    if item_from_passive == "" and items_from_items == "":
                        break
                    full_items = item_from_passive+items_from_items
                    char_from_items = {'character': items.get('character')}
                    list_json = list()
                    for item in full_items:
                        payload = {**item, **char_from_items}
                        list_json.append(payload)
                    # post_to_file(list_json)
                    post_to_splunk(list_json)
            account.extracted = True


def post_to_splunk(json_event):
    try:
        uri = "http://localhost:8088/services/collector/event"
        big_event = '{"event": %s}' % json.dumps(json_event)
        result = requests.post(uri, data=big_event, headers={"Authorization": "Splunk 40678e5e-cab1-4f12-8bb1-8d6e5176bb67"}, verify=False)
        result.raise_for_status()
    except requests.HTTPError as ex:
        LOGGER.error(ex)


def post_to_file(json_event):

    try:
        with open("output_result.logs", "a", encoding='utf-8') as writeFile:
            for item in json_event:
                big_event = '%s\n' % (json.dumps(item, ensure_ascii=False))
                writeFile.writelines(big_event)
    except requests.HTTPError as ex:
        LOGGER.error(ex)


def request_get_windows(uri):
    try:

        result = requests.get(uri)
        if result.status_code == 429:
            LOGGER.debug("too many request - waiting some time")
            time.sleep(10)
            request_get_windows(uri)
        else:
            result.encoding = 'utf-8'
            return result.json()
        # LOGGER.debug(json.dumps(result.json(), indent=4))

    except requests.HTTPError as ex:
        LOGGER.error(ex)


def request_trade_api(meta):
    try:
        LOGGER.debug("trigger trade_api with changeId %s", meta.change_id)
        uri = "https://www.pathofexile.com/api/public-stash-tabs?id=%s" % meta.change_id
        result = requests.get(uri,)
        result.raise_for_status()
        result.encoding = 'utf-8'
        extract_character(result.json(), meta)

    except requests.HTTPError as ex:
        LOGGER.error(ex)


def add_or_append_character(meta, account_name, character_name, character_league, extracted=False):
    character = Character(character_name, character_league)
    if meta.accounts.get(account_name):
        if character not in meta.accounts[account_name].characters:
            meta.accounts[account_name].characters.append(character)
    else:
        account = Account(account_name)
        meta.accounts[account_name] = account
        meta.accounts[account_name].characters.append(character)
    meta.accounts[account_name].extracted = extracted


def extract_character(req_json, meta):
    parsed_json = req_json  # json.loads(json.dumps(req_json,ensure_ascii=False,encoding="utf-8"))
    # lastCharacterName
    # accountName
    stashes = parsed_json.get("stashes")
    for stash in stashes:
        add_or_append_character(meta, stash.get("accountName"), stash.get("lastCharacterName"), stash.get('league'))
        account_name = stash.get("accountName")  # .encode('utf-8')
        if account_name and account_name != "None":
            add_or_append_character(meta, account_name, stash.get("lastCharacterName"), stash.get('league'))

    next_change_id = parsed_json.get("next_change_id")
    LOGGER.debug(next_change_id)
    if meta.change_id != next_change_id:
        meta.change_id = next_change_id
        meta.trade_api_call += 1
        if meta.trade_api_call % 100 == 0:
            save_accounts(meta)
        if meta.trade_api_call < 100:
            request_trade_api(meta)


def save_accounts(meta):
    LOGGER.debug("output to file")
    with open(PATH_TO_CHARACTER_CHECKPOINT, "w", encoding='utf-8') as outfile:
        outfile.write("account_name,character_name,character_league,extracted\n")
        for account in meta.accounts.values():
            for character in account.characters:
                line = u"{0},{1},{2},{3}\n".format(account.account_name, character.name, character.league, account.extracted)
                outfile.write(line)
    with open(PATH_TO_CHANGE_ID_CHECKPOINT, "w", encoding='utf-8') as outfile:
        outfile.write(meta.change_id)


def load_accounts(meta):
    if os.path.isfile(PATH_TO_CHARACTER_CHECKPOINT):
        with open(PATH_TO_CHARACTER_CHECKPOINT, "r", encoding='utf-8') as outfile:
            reader = csv.DictReader(outfile)
            for row in reader:
                add_or_append_character(meta, row['account_name'], row['character_name'], row['character_league'], row['extracted'])

    if os.path.isfile(PATH_TO_CHANGE_ID_CHECKPOINT):
        with open(PATH_TO_CHANGE_ID_CHECKPOINT, "r", encoding='utf-8') as outfile:
            change_id = outfile.readline()
            if change_id:
                meta.change_id = change_id


if __name__ == "__main__":
    main()

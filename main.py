#!/usr/bin/env python3

import re
from time import sleep
from os import getenv
import requests
from dotenv import load_dotenv

API_URL = "https://zh.wikipedia.org/w/api.php"
CSD_CATEGORY = "快速删除候选"
CSD_PAGE_MATCH = r"{{delete\|[rR]7}}\n"
CSD_REPLACE_TEXT = r"{{vfd|转交佛祖西来提交的R7|date=2025/06/19}}" + "\n"

BASE_REQUEST = {
    "action": "query",
    "list": "categorymembers",
    "cmtitle": "Category:" + CSD_CATEGORY,
    "cmnamespace": 0,
    "cmlimit": 20,
    "cmdir": "descending",  # To avoid conflicts with 魔琴
    "format": "json",
}


def get_pages(S: requests.Session, cmcontinue: str = ""):
    GET_PAGES_PARAMS = dict(BASE_REQUEST)
    GET_PAGES_PARAMS["cmcontinue"] = cmcontinue
    R = S.get(url=API_URL, params=GET_PAGES_PARAMS)
    DATA = R.json()
    print(DATA)

    pages = []
    for pagedata in DATA["query"]["categorymembers"]:
        pages.append(pagedata["title"])

    cmcontinue = False
    if "continue" in DATA and "cmcontinue" in DATA["continue"]:
        cmcontinue = DATA["continue"]["cmcontinue"]

    return pages, cmcontinue


def main():
    load_dotenv()
    S = requests.Session()

    BATCH_INSERT_POINT = "<!-- FilterInappropriateCSD: batch insert point " + \
        getenv('WIKI_USERNAME') + " -->"
    print(BATCH_INSERT_POINT)

    LOGIN_TOKEN_PARAMS = {
        "action": "query",
        "meta": "tokens",
        "type": "login",
        "format": "json",
    }

    R = S.get(url=API_URL, params=LOGIN_TOKEN_PARAMS)
    DATA = R.json()
    print(DATA)
    LOGIN_TOKEN = DATA['query']['tokens']['logintoken']

    LOGIN_PARAMS = {
        'action': "login",
        'lgname': getenv('WIKI_USERNAME'),
        'lgpassword': getenv('WIKI_BOTPASSWORD'),
        'lgtoken': LOGIN_TOKEN,
        'format': "json"
    }

    R = S.post(url=API_URL, data=LOGIN_PARAMS)
    DATA = R.json()
    print(DATA)
    assert DATA['login']['result'] == 'Success'

    TOKEN_PARAMS = {
        "action": "query",
        "meta": "tokens",
        "format": "json",
    }

    R = S.get(url=API_URL, params=TOKEN_PARAMS)
    DATA = R.json()
    print(DATA)
    CSRF_TOKEN = DATA['query']['tokens']['csrftoken']

    cmcontinue = ""

    while True:
        print(cmcontinue)
        if cmcontinue == False:
            return 0
        pages, cmcontinue = get_pages(S, cmcontinue)
        batch_queue = []

        GET_CONTENT_PARAMS = {
            "action": "query",
            "prop": "revisions",
            "titles": "|".join(pages),
            "rvprop": "ids|content|user",
            "rvslots": "main",
            "formatversion": "2",
            "format": "json"
        }

        R = S.get(url=API_URL, params=GET_CONTENT_PARAMS)
        DATA = R.json()
        print(DATA)

        for page_data in DATA["query"]["pages"]:
            page_revid = page_data["revisions"][0]["revid"]
            page_content = page_data["revisions"][0]["slots"]["main"]["content"]
            new_page_content = re.sub(
                CSD_PAGE_MATCH, CSD_REPLACE_TEXT, page_content)

            print("Page: " + page_data["title"])
            print("Last edited by: " + page_data["revisions"][0]["user"])
            if new_page_content != page_content:
                print(page_content)
                choice = input("Do it? (y/N/b) ")
                choice = choice.lower()[0]
                if choice == "y":
                    batch_queue.append({
                        "title": page_data["title"],
                        "newcontent": new_page_content,
                        "baseid": page_revid,
                    })
                    print()
                elif choice == "b":
                    return 0
            else:
                print("No match.")
                print()

        if len(batch_queue) == 0:
            continue

        batch_afd_content = ""

        for job in batch_queue:
            EDIT_PARAMS = {
                "action": "edit",
                "token": CSRF_TOKEN,
                "title": job["title"],
                "text": job["newcontent"],
                "summary": "半自動轉交存廢討論 (github.com/Emojigit/FilterInappropriateCSD)",
                "notminor": True,
                "baserevid": job["baseid"],
                "nocreate": True,
                "watchlist": "watch",
                "watchlistexpiry": "1 month",
                "format": "json",
            }

            R = S.post(url=API_URL, data=EDIT_PARAMS)
            DATA = R.json()
            print(DATA)

            if "error" not in DATA:
                print("Adding " + job["title"])
                batch_afd_content += "=== [[:" + job["title"] + "]] ===\n\n"

            sleep(3)

        print(batch_afd_content)

        while True:
            GET_AFD_PARAMS = {
                "action": "query",
                "prop": "revisions",
                "titles": "Wikipedia:頁面存廢討論/記錄/2025/06/19",
                "rvprop": "ids|content",
                "rvslots": "main",
                "formatversion": "2",
                "format": "json"
            }

            R = S.get(url=API_URL, params=GET_AFD_PARAMS)
            DATA = R.json()
            print(DATA)

            afd_revid = DATA["query"]["pages"][0]["revisions"][0]["revid"]
            afd_content = DATA["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
            new_afd_content = afd_content.replace(BATCH_INSERT_POINT,
                                                  batch_afd_content + BATCH_INSERT_POINT)

            if afd_content == new_afd_content:
                print("ERROR: No changes.")
                return 1

            EDIT_AFD_PARAMS = {
                "action": "edit",
                "token": CSRF_TOKEN,
                "title": "Wikipedia:頁面存廢討論/記錄/2025/06/19",
                "text": new_afd_content,
                "summary": "半自動轉交存廢討論 (github.com/Emojigit/FilterInappropriateCSD)",
                "notminor": True,
                "baserevid": afd_revid,
                "nocreate": True,
                "watchlist": "watch",
                "watchlistexpiry": "1 month",
                "format": "json",
            }

            R = S.post(url=API_URL, data=EDIT_AFD_PARAMS)
            DATA = R.json()
            print(DATA)

            if "error" not in DATA:
                break


if __name__ == "__main__":
    import sys
    sys.exit(main())

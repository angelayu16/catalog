import config
import os
import requests
import serpapi

from datetime import datetime
from utils import utils


def handle_entities(entities: list, entity_type: str):
    """
    Retrieves link for each entity and saves them to user's Notion
    database.
    """
    print(f"Handling {entity_type}...")

    # TODO: Check if Notion database exists first, create one if it doesn't
    for name, note in entities:
        # 'note' should be of the form "Shared on <platform, ..." where the
        # part following the comma contains additional context on the entity.
        # We'll include this in the query to increase our chances of grabbing
        # the right link.
        query = f"{name}{note[note.find(",")+1:]}"
        link = get_entity_link(query)
        link = utils.remove_query_from_link(link)

        # TODO: Account for duplicate entries in Notion database
        response_code = save_entity_to_notion(entity_type, name, link, note)

        if response_code != 200:
            print(f"Error saving {name} to Notion")


def get_entity_link(query: str):
    """
    Returns a link for the entity based on a Google search of its name.
    """
    client = serpapi.Client(
        api_key=os.environ["SERP_API_KEY"],
    )
    result = client.search(
        q=query,
        engine="google",
        hl="en",
        gl="us",
    )

    # Prefer a Twitter link if it exists, otherwise just grab the first result
    if "twitter_results" in result:
        link = result["twitter_results"]["link"]
    else:
        link = result["organic_results"][0]["link"]

    return link


def save_entity_to_notion(entity_type: str, name: str, link: str, note: str):
    """
    Saves the entity to a Notion database.
    """
    entry = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Type": {"rich_text": [{"text": {"content": entity_type}}]},
        "Note": {"rich_text": [{"text": {"content": note}}]},
        "Link": {"url": link},
        "Date Added": {"date": {"start": datetime.now().date().isoformat()}},
    }
    payload = {
        "parent": {"database_id": os.environ["NOTION_CATALOG_DB_KEY"]},
        "properties": entry,
    }

    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers=config.NOTION_HEADERS,
        json=payload,
    )

    return response.status_code

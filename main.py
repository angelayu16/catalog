import base64
import json
import os
import requests

from datetime import datetime

LOCAL_PHOTO_DIR = "test_dir"
VISION_PROMPT = """
Identify the location of each image. Respond only with the names of the
locations and any supplemental identifying information like address or city.
Separate by new line and do not enumerate them.

For example, the response might look like:
Mala Project, 122 1st Ave., New York, NY 10009
Black Fox Coffee, New York
Udupi Palace
"""


def encode_image(image_path: str):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_locations_from_photos(photo_dir_path: str = LOCAL_PHOTO_DIR):
    """
    Extracts locations from the photos in the given directory with GPT-4 vision.
    Returns the list of locations separated by new line.
    E.g. Mala Project
         Black Fox Coffee
         Udupi Palace
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
    }
    message_content = [{"type": "text", "text": VISION_PROMPT}]
    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "user",
            }
        ],
        "max_tokens": 300,
    }

    # Iterate through test dir, appending photos to message content
    for file_path in os.listdir(photo_dir_path):
        encoded_image = encode_image(f"{photo_dir_path}/{file_path}")
        message_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
            }
        )
    payload["messages"][0]["content"] = message_content

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
    )
    locations = response.json()["choices"][0]["message"]["content"].splitlines()

    return locations


def get_locations_in_notion():
    """
    Get names of locations already in the Notion database.
    """
    headers = {
        "Authorization": f"Bearer {os.environ['NOTION_CATALOG_SECRET']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    response = requests.post(
        f"https://api.notion.com/v1/databases/{os.environ['NOTION_LOCATION_ID']}/query",
        headers=headers,
    )

    if response.status_code != 200:
        raise Exception(f"Failed to query database: {response.text}")

    data = response.json()
    location_names = [
        result["properties"]["Name"]["title"][0]["text"]["content"]
        for result in data["results"]
        if result["properties"]["Name"]["title"]
    ]

    return location_names


def get_gmaps_info(location: str):
    """
    Retrieves a Google Maps location based on the input string and returns its
    name, address, location type, and Google Maps URL.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ["GMAPS_API_KEY"],
        "X-Goog-FieldMask": (
            "places.displayName,"
            "places.formattedAddress,"
            "places.primaryTypeDisplayName,"
            "places.googleMapsUri"
        ),
    }
    payload = {"textQuery": location}
    response = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers=headers,
        data=json.dumps(payload),
    )
    first_match = response.json()["places"][0]

    # Not all places on Google Maps are tagged with a location type
    location_type = (
        first_match["primaryTypeDisplayName"]["text"]
        if "primaryTypeDisplayName" in first_match.keys()
        else ""
    )

    return (
        first_match["displayName"]["text"],
        location_type,
        first_match["formattedAddress"],
        first_match["googleMapsUri"],
    )


def add_location_to_notion(
    name: str,
    location_type: str,
    address: str,
    gmaps_link: str,
    existing_locations: list,
):
    """
    Adds the given location to a Notion database.
    """
    # Don't add location if it already exists in the database
    if name in existing_locations:
        return

    headers = {
        "Authorization": f"Bearer {os.environ['NOTION_CATALOG_SECRET']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    new_location_data = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Location Type": {"rich_text": [{"text": {"content": location_type}}]},
        "Address": {"rich_text": [{"text": {"content": address}}]},
        "Google Maps Link": {"url": gmaps_link},
        "Date Added": {"date": {"start": datetime.now().date().isoformat()}},
    }

    payload = {
        "parent": {"database_id": os.environ["NOTION_LOCATION_ID"]},
        "properties": new_location_data,
    }
    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json=payload,
    )

    return response.status_code


if __name__ == "__main__":
    # Extract locations from photos
    locations = get_locations_from_photos()

    # Get locations already in Notion database
    existing_locations = get_locations_in_notion()

    # Retrieve Google Maps data for each location
    for location in locations:
        (
            name,
            location_type,
            address,
            gmaps_link,
        ) = get_gmaps_info(location)
        add_location_to_notion(
            name, location_type, address, gmaps_link, existing_locations
        )

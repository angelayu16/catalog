import base64
import json
import os
import requests

LOCAL_PHOTO_DIR = "test_dir"
GMAPS_API_URL = "https://places.googleapis.com/v1/places:searchText"
VISION_PROMPT = """
Identify the location of each image. Respond only with the names of the
locations separated by new lines. Do not enumerate them.

For example, the response might look like:
Mala Project
Black Fox Coffee
Udupi Palace
"""


def encode_image(image_path: str):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


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

    return (
        first_match["displayName"]["text"],
        first_match["formattedAddress"],
        first_match["primaryTypeDisplayName"]["text"],
        first_match["googleMapsUri"],
    )


if __name__ == "__main__":
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
    for file_path in os.listdir(LOCAL_PHOTO_DIR):
        encoded_image = encode_image(f"{LOCAL_PHOTO_DIR}/{file_path}")
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
    places = response.json()["choices"][0]["message"]["content"].splitlines()

    # Retrieve Google Maps data for each location
    for place in places:
        (
            displayName,
            formattedAddress,
            primaryTypeDisplayName,
            googleMapsUri,
        ) = get_gmaps_info(place)
        print(displayName)
        print(formattedAddress)
        print(primaryTypeDisplayName)
        print(googleMapsUri)
        print("-----")

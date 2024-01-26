import base64
import json
import os
import requests

from playwright.sync_api import sync_playwright

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


def get_gmaps_info(location: str):
    """
    Retrieves a Google Maps location based on the input string and returns its
    name, address, location type, and Google Maps URL.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ["GMAPS_API_KEY"],
        "X-Goog-FieldMask": ("places.displayName," "places.googleMapsUri"),
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
        first_match["googleMapsUri"],
    )


def save_locations_to_gmaps(gmaps_locations):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Go to Google login page and wait for user to log in
        page.goto("https://accounts.google.com/signin")
        page.wait_for_url("https://myaccount.google.com/*")
        print("Login successful")

        # Iterate through location links, saving each one to "Want to go" or
        # skipping if it's already saved
        for name, link in gmaps_locations:
            page.goto(link)

            # Wait for either the "Save" or "Saved" button to become visible
            save_button_selector = 'button[data-value="Save"]'
            saved_button_selector = 'button[data-value^="Saved"]'
            page.wait_for_selector(
                f"{save_button_selector}, {saved_button_selector}",
                state="visible",
            )

            if page.is_visible(save_button_selector):
                # Click "Save" and wait for response
                with page.expect_response(
                    lambda response: "/maps/preview/entitylist/createitem"
                    in response.url
                    and response.status == 200
                ) as response_info:
                    page.click(save_button_selector)

                    # Save location to "Want to go"
                    want_to_go_selector = (
                        "xpath=//div[text()='Want to go']"
                        "/ancestor::div[@role='menuitemradio']"
                    )
                    page.wait_for_selector(want_to_go_selector, state="visible")
                    page.click(want_to_go_selector)

                response = response_info.value
                if response.ok:
                    print(f"Successfully saved {name}")
                else:
                    print(f"Failed to save {name}, response: {response.status}")
            elif page.is_visible(saved_button_selector):
                print(f"{name} is already saved")
            else:
                print(f"No 'Save' or 'Saved' button found for {name}")

        browser.close()


if __name__ == "__main__":
    # Extract locations from photos
    locations = get_locations_from_photos()

    # Retrieve Google Maps data for each location
    gmaps_locations = []
    for location in locations:
        gmaps_locations.append(get_gmaps_info(location))

    # Save all locations to user's "Want to go" list in Google Maps
    save_locations_to_gmaps(gmaps_locations)

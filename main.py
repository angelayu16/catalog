import base64
import collections
import json
import os
import requests

from playwright.sync_api import sync_playwright

LOCAL_PHOTO_DIR = "test_dir"
VISION_PROMPT = """
You will be fed a set of screenshots.

Identify the location of each image. Respond only with the names of the
locations and any supplemental identifying information like address or city.
The name and other identifying information should be separated by comma.

If you can identify the source of the image, add that to the line separated by
semicolon. A source is the person or account that shared the location in the
screenshot. For example, it might be the handle of the Instagram account that
shared the place (usually right above/below a screenshotted post, or in the
upper left corner of a screenshotted Instagram story). If you can't identify the
account, you can respond with the platform it was shared on (Twitter, Instagram,
etc.), but you should try to be as specific as possible.

If there is additional information or details from the source, also add that to
the line, separated by comma + space from the source if there is one, otherwise
separated by semicolon from the location information. Additional information
might be specific dishes that are recommended at the location or anything else
that has been said about the location in the image. Enclose their commentary in
quotes.

Even if there is no additional information, you should still add a semicolon
after the location data.

So each line should be of the form:
<location>,<supplemental info>;<source>, <additional info>

There should never be two consecutive semicolons.

Separate by new line and do not enumerate them.

For example, the response might look like:
Mala Project, 122 1st Ave., New York, NY 10009;Shared on Instagram
Black Fox Coffee, New York;Shared on Twitter by @myfriend
Udupi Palace;Shared on Instagram by @myfriend, \"I love the mysore masala dosa\"
California Wine Merchant;
"""

ScreenshotData = collections.namedtuple("ScreenshotData", ["name", "link", "note"])


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
    response_content = response.json()["choices"][0]["message"]["content"]
    locations = [line for line in response_content.splitlines() if line]

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

    return first_match["displayName"]["text"], first_match["googleMapsUri"]


def login_to_google(page):
    page.goto("https://accounts.google.com/signin")
    page.wait_for_url("https://myaccount.google.com/*")
    print("Login successful")


def is_new_location(page, name, link):
    page.goto(link)
    save_button_selector = 'button[data-value="Save"]'
    saved_button_selector = 'button[data-value^="Saved"]'
    page.wait_for_selector(
        f"{save_button_selector}, {saved_button_selector}", state="visible"
    )

    if page.is_visible(save_button_selector):
        return True
    elif page.is_visible(saved_button_selector):
        print(f"{name} is already saved")
        return False
    else:
        print(f"No 'Save' or 'Saved' button found for {name}")
        return False


def save_new_location(page, name, note):
    with page.expect_response(
        lambda response: "/maps/preview/entitylist/createitem" in response.url
        and response.status == 200
    ) as response_info:
        # Click "Save"
        page.click('button[data-value="Save"]')

        # Click "Want to go" and wait for response
        want_to_go_selector = (
            "xpath=//div[text()='Want to go']" "/ancestor::div[@role='menuitemradio']"
        )
        page.wait_for_selector(want_to_go_selector, state="visible")
        page.click(want_to_go_selector)

    response = response_info.value
    if response.ok:
        print(f"Successfully saved {name}")
        add_note_to_location(page, name, note)
    else:
        print(f"Failed to save {name}, response: {response.status}")


def add_note_to_location(page, name, note):
    if not note:
        return

    # Click "Add note"
    add_note_selector = 'button[aria-label^="Add note"]'
    page.wait_for_selector(add_note_selector, state="visible")
    page.click(add_note_selector)

    # Add note to text box
    textarea_selector = page.wait_for_selector("textarea")
    textarea_selector.type(note)

    # Click "Done" and wait for response
    with page.expect_response(
        lambda response: "/maps/preview/entitylist/updateitem" in response.url
        and response.status == 200
    ) as response_info:
        page.click("text=Done")

    response = response_info.value
    if response.ok:
        print(f"Successfully added note for {name}")
    else:
        print(f"Failed to add note for {name}")


def save_locations_to_gmaps(gmaps_locations):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        login_to_google(page)

        for name, link, note in gmaps_locations:
            if is_new_location(page, name, link):
                save_new_location(page, name, note)

        browser.close()


if __name__ == "__main__":
    # Extract locations from photos
    locations = get_locations_from_photos()

    # Retrieve Google Maps data for each location
    screenshot_data = []
    for location in locations:
        data = location.split(";")
        location_data = data[0]
        note = data[1]

        name, link = get_gmaps_info(location_data)
        screenshot_data.append(ScreenshotData(name=name, link=link, note=note))

    # Save all locations to user's "Want to go" list in Google Maps
    save_locations_to_gmaps(screenshot_data)

import base64
import collections
import json
import mimetypes
import os
import requests

from playwright.sync_api import sync_playwright

LOCAL_PHOTO_DIR = "test_dir"
VISION_PROMPT = """
You will be fed a set of screenshots. They should be references to a location,
person, or company. Identify what location, person, or company is in the image,
i.e. what the subject of the image is. I want you to respond with a line of the
following form for each screenshot:

<subject type>;<subject name>;<source>, <additional source info>

Let's break down each part of the line:

<subject type> -> Choose from "LOCATION", "PERSON", "COMPANY", or "UNKNOWN" if
it's not clear.

<subject name> -> The name of the location, person, or company. If it's a
location, you can also include any supplemental identifying information (like
city or address).

<source> -> The person or account that shared the subject. For example, the
handle of the Instagram account that shared the subject (usually in the upper
left corner of an Instagram story or right above/below a screenshotted post).
Or it could be the handle of the Twitter account that shared the subject
(usually right above the screenshotted Tweet). If you can't identify the
account, you can respond with the platform it was shared on (Twitter, Instagram,
etc.), but you should try to be as specific as possible.

<additional source info> -> Any additional information about the subject,
separated from the source by a comma + space. For a location, this might be
specific dishes that are recommended or anything else that has been said about
it. For a person, it might be where they work or anything notable about them.
For a company, it might be a description of what the company does. Enclose any
commentary from the source in quotes.

You should end up with one line per image, separated by new line. Do not
enumerate them.

For example, the response might look like:
LOCATION;Mala Project, 122 1st Ave., New York, NY 10009;Shared on Instagram
PERSON;Anthony Bourdain;Shared on Twitter
LOCATION;Black Fox Coffee, New York;Shared on Twitter by @myfriend
COMPANY;OpenAI;Shared on Twitter, U.S. based AI research organization
LOCATION;Udupi Palace;Shared on Instagram by @myfriend, \"Get the podi dosa!\"
"""

ScreenshotData = collections.namedtuple("ScreenshotData", ["name", "link", "note"])


def encode_image(image_path: str):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_subjects_from_photos(photo_dir_path: str = LOCAL_PHOTO_DIR):
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
        if file_path == ".DS_Store":
            continue

        encoded_image = encode_image(f"{photo_dir_path}/{file_path}")
        mime_type, _ = mimetypes.guess_type(file_path)
        file_type = mime_type.split("/")[-1]

        message_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/{file_type};base64,{encoded_image}"},
            }
        )
    payload["messages"][0]["content"] = message_content

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
    )
    response_content = response.json()["choices"][0]["message"]["content"]
    subjects = [line for line in response_content.splitlines() if line]

    return subjects


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
    subjects = get_subjects_from_photos()
    locations = []
    people = []
    companies = []

    for subject in subjects:
        parts = subject.split(";")
        subject_type = parts[0]
        subject_name = parts[1]
        subject_source = parts[2]

        if subject_type == "LOCATION":
            # Retrieve location name and link from Google Maps
            name, link = get_gmaps_info(subject_name)
            locations.append(ScreenshotData(name=name, link=link, note=subject_source))
        elif subject_type == "PERSON":
            people.append((subject_name, subject_source))
        elif subject_type == "COMPANY":
            companies.append((subject_name, subject_source))
        else:
            print(f"Unknown type {subject_type} for {subject_name}")

    save_locations_to_gmaps(locations)
    # TODO: Save people to Notion database
    # TODO: Save companies to Notion database

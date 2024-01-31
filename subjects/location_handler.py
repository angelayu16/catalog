import collections
import config
import json
import requests

from playwright.sync_api import sync_playwright, Page

Location = collections.namedtuple("Location", ["name", "link", "note"])


def handle_locations(locations: list):
    """
    Given the input list of locations, extracts the Google Maps data for each
    one and then saves them to the user's Google Maps list.
    """
    gmaps_locations = []

    for name, note in locations:
        gmaps_name, gmaps_link = get_gmaps_info(name)
        gmaps_locations.append(Location(name=gmaps_name, link=gmaps_link, note=note))

    save_locations_to_gmaps(gmaps_locations)


def get_gmaps_info(name: str):
    """
    Retrieves a Google Maps location based on the input string and returns its
    name and Google Maps URL.
    """
    response = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers=config.GMAPS_HEADERS,
        data=json.dumps({"textQuery": name}),
    )
    first_match = response.json()["places"][0]

    return first_match["displayName"]["text"], first_match["googleMapsUri"]


def save_locations_to_gmaps(gmaps_locations):
    """
    Uses browser automation to save input list of locations to user's Google
    Maps list.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        login_to_google(page)

        for name, link, note in gmaps_locations:
            if is_new_location(page, name, link):
                save_new_location(page, name, note)

        browser.close()


def login_to_google(page: Page):
    """
    Navigates to Google login page and waits for user to log in.
    """
    page.goto("https://accounts.google.com/signin")
    page.wait_for_url("https://myaccount.google.com/*")
    print("Login successful")


def is_new_location(page: Page, name: str, link: str):
    """
    Navigates to the Google Maps link for the given location. Returns True if
    the location hasn't been previously saved to the user's Google Maps lists,
    False otherwise.
    """
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
    """
    Saves the current Google Maps link on 'page' to the user's "Want to go"
    list with the given note.
    """
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

    # Make sure response was good before adding note
    response = response_info.value
    if response.ok:
        print(f"Successfully saved {name}")
        add_note_to_location(page, name, note)
    else:
        print(f"Failed to save {name}, response: {response.status}")


def add_note_to_location(page, name, note):
    """
    Adds the input note to the saved location on 'page'.
    """
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

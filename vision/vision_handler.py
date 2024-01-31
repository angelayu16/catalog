import config
import os
import requests

from utils import utils

VISION_PROMPT = """
You will be fed a set of screenshots. They should be references to a location,
person, or company. Identify what location, person, or company is in the image,
i.e. what the subject of the image is. I want you to respond with a line of the
following form for each screenshot:

<subject type>;<subject name>;<source>, <additional source info>

Let's break down each part of the line:

<subject type> -> Choose from "location", "person", "company", or "unknown" if
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
location;Mala Project, 122 1st Ave., New York, NY 10009;Shared on Instagram
person;Anthony Bourdain;Shared on Twitter
location;Black Fox Coffee, New York;Shared on Twitter by @myfriend
company;OpenAI;Shared on Twitter, U.S. based AI research organization
location;Udupi Palace;Shared on Instagram by @myfriend, \"Get the podi dosa!\"
"""


def get_subjects_from_photos(photo_dir_path: str = config.LOCAL_PHOTO_DIR):
    """
    Extracts locations from the photos in the given directory with GPT-4 vision.
    Returns the list of locations separated by new line.
    E.g. Mala Project
         Black Fox Coffee
         Udupi Palace
    """
    print("Handling photos...")

    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "user",
            }
        ],
        "max_tokens": 300,
    }
    message_content = [{"type": "text", "text": VISION_PROMPT}]

    # Iterate through test directory, appending photos to message content
    for file_path in os.listdir(photo_dir_path):
        if file_path == ".DS_Store":
            continue

        image = utils.encode_image(f"{photo_dir_path}/{file_path}")
        file_type = utils.get_file_type(file_path)

        message_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/{file_type};base64,{image}"},
            }
        )
    payload["messages"][0]["content"] = message_content

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=config.OPENAI_HEADERS,
        json=payload,
    )
    response_content = response.json()["choices"][0]["message"]["content"]
    subjects = [line for line in response_content.splitlines() if line]

    return subjects

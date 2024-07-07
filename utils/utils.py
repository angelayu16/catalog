import base64
import mimetypes
import re


def encode_image(image_path: str):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_file_type(file_path: str):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type.split("/")[-1]


def remove_query_from_link(link):
    return link.split("?")[0]


def get_handle_from_note(note: str):
    # Looks for "@" followed by characters
    match = re.search(r"@(\w+)", note)
    return match.group(1) if match else None

import os

LOCAL_PHOTO_DIR = "test_dir"

GMAPS_HEADERS = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": os.environ["GMAPS_API_KEY"],
    "X-Goog-FieldMask": ("places.displayName," "places.googleMapsUri"),
}

NOTION_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.environ["NOTION_CATALOG_KEY"]}",
    "Notion-Version": "2022-06-28",
}

OPENAI_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
}

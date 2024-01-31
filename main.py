from subjects import entity_handler
from subjects import location_handler
from vision import vision_handler


def categorize_subjects(subjects: list):
    """
    Parses data on each subject and splits them into lists based on type.
    """
    locations = []
    people = []
    companies = []

    for subject in subjects:
        parts = subject.split(";")
        subject_type = parts[0]
        subject_name = parts[1]
        subject_note = parts[2]

        if subject_type == "location":
            locations.append((subject_name, subject_note))
        elif subject_type == "person":
            people.append((subject_name, subject_note))
        elif subject_type == "company":
            companies.append((subject_name, subject_note))
        else:
            # TODO: Test with input images of unwanted subjects
            print(f"Unknown type {subject_type} for {subject_name}")

    return locations, people, companies


def main():
    subjects = vision_handler.get_subjects_from_photos()

    locations, people, companies = categorize_subjects(subjects)

    location_handler.handle_locations(locations)
    entity_handler.handle_entities(people, "person")
    entity_handler.handle_entities(companies, "company")

    print("Completed script")


if __name__ == "__main__":
    main()

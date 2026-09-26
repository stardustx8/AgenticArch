from .reader import read_contacts
from .validate import validate_contact


def import_contacts(text):
    """Return (valid_rows, errors); errors is a list of (row_number, messages)."""
    valid, errors = [], []
    for number, row in enumerate(read_contacts(text), start=1):
        problems = validate_contact(row)
        if problems:
            errors.append((number, problems))
        else:
            valid.append(row)
    return valid, errors

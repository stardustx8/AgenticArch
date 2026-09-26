import json


def load_rows(text):
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("expected a JSON array of records")
    return data

import json

from .flatten import flatten


def flatten_json_text(text, sep="."):
    """Flatten a JSON document given as text and return it as sorted JSON text."""
    return json.dumps(flatten(json.loads(text), sep=sep), sort_keys=True)

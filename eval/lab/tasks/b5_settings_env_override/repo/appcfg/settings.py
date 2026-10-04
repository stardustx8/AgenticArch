import json

DEFAULTS = {
    'debug': False,
    'workers': 4,
    'log_level': 'info',
    'bind': '127.0.0.1:8000',
}


def load_file(path):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        return {}
    if type(data) != dict:
        return {}
    return data


def load(path=None):
    """Build the effective settings: defaults, then the JSON file if given."""
    settings = dict(DEFAULTS)
    if path:
        settings.update(load_file(path))
    return settings

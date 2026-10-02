import json
import os

DEFAULTS = {
    'debug': False,
    'workers': 4,
    'log_level': 'info',
    'bind': '127.0.0.1:8000',
}

ENV_PREFIX = 'APP_'
_TRUE = {'1', 'true', 'yes'}
_FALSE = {'0', 'false', 'no'}


def load_file(path):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        return {}
    if type(data) != dict:
        return {}
    return data


def _coerce(key, raw, default):
    if isinstance(default, bool):
        lowered = raw.strip().lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise ValueError(f'invalid boolean for {key}: {raw!r}')
    if isinstance(default, int):
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f'invalid integer for {key}: {raw!r}') from None
    return raw


def load_env(environ):
    """Overrides taken from APP_<KEY> variables, for keys known in DEFAULTS."""
    overrides = {}
    for key, default in DEFAULTS.items():
        name = ENV_PREFIX + key.upper()
        if name in environ:
            overrides[key] = _coerce(key, environ[name], default)
    return overrides


def load(path=None, environ=None):
    """Build the effective settings: defaults, then the JSON file if given,
    then APP_* environment variables."""
    if environ is None:
        environ = os.environ
    settings = dict(DEFAULTS)
    if path:
        settings.update(load_file(path))
    settings.update(load_env(environ))
    return settings

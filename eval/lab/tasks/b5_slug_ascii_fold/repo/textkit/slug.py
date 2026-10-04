import re

_NON_ALNUM = re.compile(r'[^a-z0-9]+')


def slugify(text, sep='-'):
    """Turn arbitrary text into a URL slug."""
    text = text.lower()
    text = _NON_ALNUM.sub(sep, text)
    return text.strip(sep)

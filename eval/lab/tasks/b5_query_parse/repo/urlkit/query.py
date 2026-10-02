from urllib.parse import quote


def _encode(value):
    return quote(str(value), safe='')


def build_query(params):
    """Encode a dict as a query string.

    List values produce the key once per element, in order.
    """
    parts = []
    for key, value in params.items():
        values = value if isinstance(value, list) else [value]
        for item in values:
            parts.append(_encode(key) + '=' + _encode(item))
    return '&'.join(parts)

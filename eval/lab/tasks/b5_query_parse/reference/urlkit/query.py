from urllib.parse import quote, unquote


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


def parse_query(qs):
    """Decode a query string produced by build_query.

    Keys seen once map to a string; repeated keys map to a list of their
    values in order.  Blank values are kept.
    """
    if qs.startswith('?'):
        qs = qs[1:]
    result = {}
    for pair in qs.split('&'):
        if not pair:
            continue
        raw_key, _, raw_value = pair.partition('=')
        key = unquote(raw_key)
        value = unquote(raw_value)
        if key not in result:
            result[key] = value
        elif isinstance(result[key], list):
            result[key].append(value)
        else:
            result[key] = [result[key], value]
    return result

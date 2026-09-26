def _needs_quotes(value):
    return value == '' or value != value.strip() or ' ' in value


def dump_env(mapping):
    """Serialize a mapping to .env text, one KEY=value per line."""
    lines = []
    for key, value in mapping.items():
        value = str(value)
        if _needs_quotes(value):
            value = f'"{value}"'
        lines.append(f'{key}={value}')
    return '\n'.join(lines) + ('\n' if lines else '')


def _unquote(value):
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def load_env(text):
    """Parse .env text (as written by dump_env) back into a dict."""
    result = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep:
            raise ValueError(f'line {lineno}: expected KEY=value')
        result[key.strip()] = _unquote(value.strip())
    return result

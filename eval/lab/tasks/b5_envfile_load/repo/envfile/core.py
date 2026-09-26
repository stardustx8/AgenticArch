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

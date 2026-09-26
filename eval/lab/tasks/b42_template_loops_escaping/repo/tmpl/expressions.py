from .errors import TemplateSyntaxError


class Expression:
    """A dotted variable path followed by zero or more filters."""

    def __init__(self, path, filters):
        self.path = path
        self.filters = filters

    def evaluate(self, context, filter_table):
        value = context.resolve(self.path)
        for name, args in self.filters:
            try:
                func = filter_table[name]
            except KeyError:
                raise TemplateSyntaxError(f'unknown filter {name!r}') from None
            value = func(value, *args)
        return value


def parse_expression(text):
    """Parse ``name.attr|filter|filter(arg)``; arguments are string or int literals."""
    parts = _split_pipes(text)
    path = parts[0].strip()
    if not path or not all(p.isidentifier() for p in path.split('.')):
        raise TemplateSyntaxError(f'bad expression {text!r}')
    return Expression(path, [_parse_filter(p.strip()) for p in parts[1:]])


def _split_pipes(text):
    parts, current, quote = [], [], None
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == '|':
            parts.append(''.join(current))
            current = []
            continue
        current.append(ch)
    parts.append(''.join(current))
    return parts


def _parse_filter(text):
    name, paren, rest = text.partition('(')
    name = name.strip()
    if not name.isidentifier():
        raise TemplateSyntaxError(f'bad filter {text!r}')
    if not paren:
        return name, ()
    if not rest.endswith(')'):
        raise TemplateSyntaxError(f'unclosed filter arguments in {text!r}')
    inner = rest[:-1].strip()
    if not inner:
        return name, ()
    return name, (_literal(inner),)


def _literal(text):
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        raise TemplateSyntaxError(f'filter arguments must be string or int literals: {text!r}') from None

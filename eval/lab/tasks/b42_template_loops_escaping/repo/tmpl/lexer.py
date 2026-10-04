from .errors import TemplateSyntaxError

TEXT = 'text'
VAR = 'var'
BLOCK = 'block'

_CLOSERS = {'{{': '}}', '{%': '%}'}


def tokenize(source):
    """Split ``source`` into (kind, value) tokens; tag values are stripped."""
    tokens = []
    pos = 0
    while pos < len(source):
        start = _next_open(source, pos)
        if start == -1:
            tokens.append((TEXT, source[pos:]))
            break
        if start > pos:
            tokens.append((TEXT, source[pos:start]))
        opener = source[start:start + 2]
        end = source.find(_CLOSERS[opener], start + 2)
        if end == -1:
            raise TemplateSyntaxError(f'unclosed {opener!r} at offset {start}')
        kind = VAR if opener == '{{' else BLOCK
        tokens.append((kind, source[start + 2:end].strip()))
        pos = end + 2
    return tokens


def _next_open(source, pos):
    found = [i for i in (source.find('{{', pos), source.find('{%', pos)) if i != -1]
    return min(found) if found else -1

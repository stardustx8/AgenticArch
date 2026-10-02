from .escaping import Markup, escape_text


def do_upper(value):
    return str(value).upper()


def do_lower(value):
    return str(value).lower()


def do_title(value):
    return str(value).title()


def do_trim(value):
    return str(value).strip()


def do_length(value):
    return len(value)


def do_join(value, sep=''):
    return sep.join(str(v) for v in value)


def do_truncate(value, length=20):
    text = str(value)
    if len(text) <= length:
        return text
    return text[:max(length - 3, 0)] + '...'


def do_safe(value):
    return Markup(str(value))


def do_escape(value):
    # Unlike autoescaping this also escapes Markup, so it goes straight to escape_text().
    return Markup(escape_text(str(value)))


BUILTIN_FILTERS = {
    'upper': do_upper,
    'lower': do_lower,
    'title': do_title,
    'trim': do_trim,
    'length': do_length,
    'join': do_join,
    'truncate': do_truncate,
    'safe': do_safe,
    'escape': do_escape,
    'e': do_escape,
}

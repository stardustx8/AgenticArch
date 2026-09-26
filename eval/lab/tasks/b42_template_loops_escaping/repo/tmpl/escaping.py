class Markup(str):
    """A string that is already safe to emit as HTML."""


_REPLACEMENTS = (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'))


def escape(value):
    """HTML-escape ``value`` unless it is already Markup."""
    if isinstance(value, Markup):
        return value
    text = str(value)
    for old, new in _REPLACEMENTS:
        text = text.replace(old, new)
    return Markup(text)

class Markup(str):
    """A string that is already safe to emit as HTML."""


_REPLACEMENTS = (
    ('&', '&amp;'),  # must come first so the other entities are not re-escaped
    ('<', '&lt;'),
    ('>', '&gt;'),
    ('"', '&quot;'),
    ("'", '&#39;'),
)


def escape_text(text):
    """Escape the HTML special characters in a plain string."""
    for old, new in _REPLACEMENTS:
        text = text.replace(old, new)
    return text


def escape(value):
    """HTML-escape ``value`` unless it is already Markup."""
    if isinstance(value, Markup):
        return value
    return Markup(escape_text(str(value)))

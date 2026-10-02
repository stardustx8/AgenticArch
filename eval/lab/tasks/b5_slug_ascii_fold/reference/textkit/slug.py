import re
import unicodedata

_NON_ALNUM = re.compile(r'[^a-z0-9]+')


def _fold_accents(text):
    decomposed = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in decomposed if not unicodedata.combining(ch))


def slugify(text, sep='-'):
    """Turn arbitrary text into a URL slug.

    Accented letters are folded to their ASCII base letter; anything else
    outside a-z/0-9 acts as a separator.
    """
    text = _fold_accents(text).lower()
    text = _NON_ALNUM.sub(sep, text)
    return text.strip(sep)

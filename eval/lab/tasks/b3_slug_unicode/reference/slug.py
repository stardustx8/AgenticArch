import unicodedata


def slugify(text, max_length=None):
    # Lowercase ASCII slug: accented letters are transliterated, other non-ASCII
    # characters are dropped, and runs of anything else become single hyphens.
    ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    words = []
    current = []
    for ch in ascii_text.lower():
        if ch.isalnum():
            current.append(ch)
        elif current:
            words.append(''.join(current))
            current = []
    if current:
        words.append(''.join(current))
    slug = '-'.join(words)
    if max_length is not None:
        slug = truncate_slug(slug, max_length)
    return slug


def truncate_slug(slug, max_length):
    # Cut at the last hyphen that fits; hard-cut only when the first word is too long.
    if len(slug) <= max_length:
        return slug
    cut = slug[:max_length + 1].rfind('-')
    if cut > 0:
        return slug[:cut]
    return slug[:max_length]

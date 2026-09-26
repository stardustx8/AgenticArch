from slug import slugify, truncate_slug


def unique_slug(title, existing, max_length=None):
    # Slug for title that is not in `existing`, adding -2, -3, ... as needed.
    # With max_length the whole result, suffix included, fits within the limit.
    base = slugify(title, max_length) or 'untitled'
    if max_length is not None:
        base = truncate_slug(base, max_length)
    slug = base
    n = 2
    while slug in existing:
        suffix = '-%d' % n
        if max_length is None:
            stem = base
        else:
            stem = truncate_slug(base, max_length - len(suffix))
        slug = stem + suffix
        n += 1
    return slug

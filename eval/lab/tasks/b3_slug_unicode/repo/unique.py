from slug import slugify


def unique_slug(title, existing):
    # Slug for title that is not in `existing`, adding -2, -3, ... as needed.
    base = slugify(title) or 'untitled'
    slug = base
    n = 2
    while slug in existing:
        slug = '%s-%d' % (base, n)
        n += 1
    return slug

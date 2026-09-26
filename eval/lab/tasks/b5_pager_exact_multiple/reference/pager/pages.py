def page_count(total, per_page):
    """Number of pages needed to show ``total`` items."""
    if per_page <= 0:
        raise ValueError('per_page must be positive')
    return -(-total // per_page)


def page_slice(items, page, per_page):
    """Items shown on 1-based ``page``."""
    start = (page - 1) * per_page
    return items[start:start + per_page]


def has_prev(page):
    return page > 1


def has_next(page, total, per_page):
    """True if there is a page after ``page``."""
    return page * per_page < total


def last_page_size(total, per_page):
    """Number of items on the final page."""
    if total <= 0:
        return 0
    return total % per_page or per_page


def page_numbers(total, per_page):
    return list(range(1, page_count(total, per_page) + 1))

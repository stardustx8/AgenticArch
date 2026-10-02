from roman import from_roman, to_roman


def page_label(index, front_matter):
    # Pages 1..front_matter are numbered i, ii, iii...; the body restarts at 1.
    if index < 1:
        raise ValueError('page index starts at 1')
    if index <= front_matter:
        return to_roman(index).lower()
    return str(index - front_matter)


def page_index(label, front_matter):
    # Inverse of page_label.
    if label.isdigit():
        return int(label) + front_matter
    n = from_roman(label)
    if n > front_matter:
        raise ValueError('no front matter page %r' % (label,))
    return n

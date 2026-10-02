def filter_by_level(entries, min_level):
    return [e for e in entries if e.level == min_level]


def filter_by_text(entries, needle):
    return [e for e in entries if needle in e.message]

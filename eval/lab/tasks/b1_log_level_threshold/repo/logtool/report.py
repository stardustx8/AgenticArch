from collections import Counter


def count_by_level(entries):
    return dict(Counter(e.level for e in entries))

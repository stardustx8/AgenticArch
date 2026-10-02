from intervals import merge_intervals


def total_covered(intervals):
    return sum(end - start for start, end in merge_intervals(intervals))


def gaps(intervals, lo, hi):
    # Uncovered sub-ranges of [lo, hi), in order.
    result = []
    cursor = lo
    for start, end in merge_intervals(intervals):
        if end <= lo or start >= hi:
            continue
        if start > cursor:
            result.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < hi:
        result.append((cursor, hi))
    return result

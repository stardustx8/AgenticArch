def merge_intervals(intervals):
    # Merge half-open [start, end) intervals into a new sorted list of tuples.
    merged = []
    for start, end in sorted(intervals):
        if start > end:
            raise ValueError('interval start after end: %r' % ((start, end),))
        if merged and start <= merged[-1][1]:
            # An interval nested inside the previous one must not shrink it.
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged

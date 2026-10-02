from pathkit.normalize import normalize, split_parts


def relative_to(path, start):
    # Relative path that leads from directory `start` to `path`. Both must be absolute,
    # or both relative to the same (unknown) directory.
    path = normalize(path)
    start = normalize(start)
    if path.startswith('/') != start.startswith('/'):
        raise ValueError('cannot mix absolute and relative paths: %r and %r' % (path, start))
    path_parts = split_parts(path)
    start_parts = split_parts(start)
    common = 0
    while (common < len(path_parts) and common < len(start_parts)
           and path_parts[common] == start_parts[common]):
        common += 1
    climb = start_parts[common:]
    if '..' in climb:
        # We would need the names of the directories above the starting point.
        raise ValueError('cannot compute a path from %r to %r' % (start, path))
    return '/'.join(['..'] * len(climb) + path_parts[common:]) or '.'

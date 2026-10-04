from pathkit.normalize import normalize, split_parts


def relative_to(path, start):
    # Relative path that leads from directory `start` to `path`.
    path_parts = split_parts(normalize(path))
    start_parts = split_parts(normalize(start))
    common = 0
    while (common < len(path_parts) and common < len(start_parts)
           and path_parts[common] == start_parts[common]):
        common += 1
    ups = ['..'] * (len(start_parts) - common)
    return '/'.join(ups + path_parts[common:]) or '.'

# POSIX-style path helpers that work on plain strings (no filesystem access).


def split_parts(path):
    # Non-empty segments, with '.' segments removed.
    return [part for part in path.split('/') if part and part != '.']


def normalize(path):
    # Collapse '.', '..' and repeated slashes. Trailing slashes are dropped.
    absolute = path.startswith('/')
    stack = []
    for part in split_parts(path):
        if part == '..':
            if stack:
                stack.pop()
        else:
            stack.append(part)
    body = '/'.join(stack)
    if absolute:
        return '/' + body
    return body or '.'

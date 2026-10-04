# POSIX-style path helpers that work on plain strings (no filesystem access).


def split_parts(path):
    # Non-empty segments, with '.' segments removed.
    return [part for part in path.split('/') if part and part != '.']


def normalize(path):
    # Collapse '.', '..' and repeated slashes. Trailing slashes are dropped.
    # Leading '..' segments of a relative path cannot be collapsed and are kept;
    # '..' at the root of an absolute path stays at the root.
    absolute = path.startswith('/')
    stack = []
    for part in split_parts(path):
        if part == '..':
            if stack and stack[-1] != '..':
                stack.pop()
            elif not absolute:
                stack.append('..')
        else:
            stack.append(part)
    body = '/'.join(stack)
    if absolute:
        return '/' + body
    return body or '.'

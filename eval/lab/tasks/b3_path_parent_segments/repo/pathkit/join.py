from pathkit.normalize import normalize


def join(*parts):
    # Join segments like os.path.join (an absolute part restarts the path), then normalize.
    result = ''
    for part in parts:
        if part.startswith('/'):
            result = part
        elif result and not result.endswith('/'):
            result = result + '/' + part
        else:
            result = result + part
    return normalize(result)

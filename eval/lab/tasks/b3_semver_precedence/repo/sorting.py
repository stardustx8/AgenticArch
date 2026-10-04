from version import Version


def sort_versions(texts):
    # Sort version strings by precedence (stable for equal precedence).
    return sorted(texts, key=Version.parse)


def latest(texts, include_prerelease=False):
    # Original text of the highest version, or None.
    best_text = None
    best = None
    for text in texts:
        version = Version.parse(text)
        if version.prerelease and not include_prerelease:
            continue
        if best is None or version > best:
            best_text, best = text, version
    return best_text

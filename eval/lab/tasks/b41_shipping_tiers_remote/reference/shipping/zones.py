from .rates import REMOTE_PREFIXES


class InvalidPostalCode(ValueError):
    pass


def normalize_zip(code):
    '''Five-digit ZIP from 12345, padded input or ZIP+4 (12345-6789).'''
    cleaned = code.strip().split('-', 1)[0]
    if len(cleaned) != 5 or not cleaned.isdigit():
        raise InvalidPostalCode(code)
    return cleaned


def is_remote(destination):
    '''True when the destination is in a remote delivery area.'''
    return normalize_zip(destination)[:3] in REMOTE_PREFIXES


def zone_for(origin, destination):
    '''Zone 1 inside the same 3-digit area, otherwise 2-5 by distance between ZIP regions.

    Remote destinations are always zone 5, wherever the parcel ships from.'''
    origin = normalize_zip(origin)
    destination = normalize_zip(destination)
    if destination[:3] in REMOTE_PREFIXES:
        return 5
    if origin[:3] == destination[:3]:
        return 1
    distance = abs(int(origin[0]) - int(destination[0]))
    return min(5, 2 + distance // 2)

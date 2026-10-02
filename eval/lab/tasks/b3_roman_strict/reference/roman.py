_NUMERALS = [
    (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
    (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
    (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'),
]
_SYMBOLS = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}


def to_roman(n):
    if not 1 <= n <= 3999:
        raise ValueError('out of range (1..3999): %r' % (n,))
    parts = []
    for value, numeral in _NUMERALS:
        count, n = divmod(n, value)
        parts.append(numeral * count)
    return ''.join(parts)


def from_roman(text):
    # Only canonical numerals (exactly what to_roman produces) are accepted, in any case.
    upper = text.upper()
    if not upper or any(ch not in _SYMBOLS for ch in upper):
        raise ValueError('invalid roman numeral: %r' % (text,))
    total = 0
    prev = 0
    for ch in reversed(upper):
        value = _SYMBOLS[ch]
        if value < prev:
            total -= value
        else:
            total += value
            prev = value
    if not 1 <= total <= 3999 or to_roman(total) != upper:
        raise ValueError('non-canonical roman numeral: %r' % (text,))
    return total

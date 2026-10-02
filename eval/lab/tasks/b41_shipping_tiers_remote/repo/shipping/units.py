import math
from decimal import Decimal

GRAMS_PER = {
    'g': Decimal('1'),
    'kg': Decimal('1000'),
    'lb': Decimal('453.59237'),
    'oz': Decimal('28.349523125'),
}
CM_PER = {'cm': Decimal('1'), 'in': Decimal('2.54')}


class UnknownUnit(ValueError):
    pass


def _decimal(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def to_grams(value, unit):
    '''Weight in whole grams, always rounded up (we never bill below the real weight).'''
    try:
        factor = GRAMS_PER[unit]
    except KeyError:
        raise UnknownUnit(unit) from None
    grams = _decimal(value) * factor
    if grams <= 0:
        raise ValueError('weight must be positive')
    return math.ceil(grams)


def to_cm(value, unit):
    try:
        factor = CM_PER[unit]
    except KeyError:
        raise UnknownUnit(unit) from None
    return _decimal(value) * factor

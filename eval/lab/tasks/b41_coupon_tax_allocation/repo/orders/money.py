from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal('0.01')


def to_money(value):
    '''Round to whole cents, half up.'''
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(CENT, rounding=ROUND_HALF_UP)

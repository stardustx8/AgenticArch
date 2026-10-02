from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal('0.01')


def to_decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(amount):
    '''Round to whole cents, half up (the rounding mode we use for all money).'''
    return to_decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)

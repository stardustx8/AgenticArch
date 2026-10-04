from decimal import Decimal

from .money import quantize_money, to_decimal


class PercentOff:
    '''Percentage off every line.'''
    kind = 'percent'

    def __init__(self, percent):
        self.value = to_decimal(percent)

    def apply(self, lines):
        '''Set ``discount`` on each (already priced) line.'''
        for line in lines:
            line.discount = quantize_money(line.line_total * self.value / 100)


COUPON_KINDS = {PercentOff.kind: PercentOff}


def coupon_from_dict(data):
    if data is None:
        return None
    return COUPON_KINDS[data['kind']](data['value'])


def coupon_to_dict(coupon):
    if coupon is None:
        return None
    return {'kind': coupon.kind, 'value': str(coupon.value)}

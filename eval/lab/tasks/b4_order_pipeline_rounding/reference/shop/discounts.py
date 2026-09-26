from decimal import ROUND_DOWN, Decimal

from .money import CENT, quantize_money, to_decimal


class PercentOff:
    '''Percentage off every line.'''
    kind = 'percent'

    def __init__(self, percent):
        self.value = to_decimal(percent)

    def apply(self, lines):
        '''Set ``discount`` on each (already priced) line.'''
        for line in lines:
            line.discount = quantize_money(line.line_total * self.value / 100)


class AmountOff:
    '''A fixed amount off the order, spread over the lines by line total.

    Each line gets its proportional share rounded down to the cent; the leftover
    cents go to the largest line (the first one on ties).  The discount never
    exceeds the order subtotal.
    '''
    kind = 'amount'

    def __init__(self, amount):
        self.value = to_decimal(amount)

    def apply(self, lines):
        subtotal = sum((line.line_total for line in lines), Decimal('0'))
        if subtotal <= 0:
            for line in lines:
                line.discount = Decimal('0')
            return
        amount = min(quantize_money(self.value), subtotal)
        for line in lines:
            share = amount * line.line_total / subtotal
            line.discount = share.quantize(CENT, rounding=ROUND_DOWN)
        leftover = amount - sum((line.discount for line in lines), Decimal('0'))
        if leftover:
            largest = max(lines, key=lambda line: line.line_total)
            largest.discount += leftover


COUPON_KINDS = {PercentOff.kind: PercentOff, AmountOff.kind: AmountOff}


def coupon_from_dict(data):
    if data is None:
        return None
    return COUPON_KINDS[data['kind']](data['value'])


def coupon_to_dict(coupon):
    if coupon is None:
        return None
    return {'kind': coupon.kind, 'value': str(coupon.value)}

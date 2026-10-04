from decimal import Decimal

from .money import to_money

ZERO = Decimal('0')


class UnknownCoupon(KeyError):
    pass


class PercentCoupon:
    def __init__(self, code, percent, category=None):
        self.code = code
        self.percent = Decimal(str(percent))
        self.category = category

    def applies_to(self, line):
        return self.category is None or line.category == self.category

    def allocate(self, amounts):
        '''Discount taken off each of the given remaining line amounts, rounded per line.'''
        shares = []
        for amount in amounts:
            if amount <= 0:
                shares.append(ZERO)
            else:
                shares.append(min(amount, to_money(amount * self.percent / 100)))
        return shares


class FixedCoupon:
    def __init__(self, code, amount, category=None):
        self.code = code
        self.amount = to_money(amount)
        self.category = category

    def applies_to(self, line):
        return self.category is None or line.category == self.category

    def allocate(self, amounts):
        '''Split the coupon over the amounts still above zero, in proportion to them.

        Capped at what is left; every share is rounded to the cent except the last
        open line's, which takes whatever is left of the coupon.'''
        shares = [ZERO] * len(amounts)
        open_lines = [i for i, amount in enumerate(amounts) if amount > 0]
        available = sum((amounts[i] for i in open_lines), ZERO)
        target = min(self.amount, available)
        if not open_lines or target <= 0:
            return shares
        given = ZERO
        for i in open_lines[:-1]:
            shares[i] = to_money(target * amounts[i] / available)
            given += shares[i]
        shares[open_lines[-1]] = target - given
        return shares


class CouponBook:
    def __init__(self, coupons=()):
        self._coupons = {coupon.code.upper(): coupon for coupon in coupons}

    def get(self, code):
        try:
            return self._coupons[code.strip().upper()]
        except KeyError:
            raise UnknownCoupon(code) from None


def default_coupons():
    return CouponBook([
        PercentCoupon('TENOFF', 10),
        FixedCoupon('SAVE5', '5.00'),
        FixedCoupon('HOME20', '20.00', category='home'),
        PercentCoupon('BOOKS15', 15, category='books'),
    ])

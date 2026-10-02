from decimal import Decimal

from .money import to_money


class UnknownCoupon(KeyError):
    pass


class PercentCoupon:
    def __init__(self, code, percent, category=None):
        self.code = code
        self.percent = Decimal(str(percent))
        self.category = category

    def applies_to(self, line):
        return self.category is None or line.category == self.category

    def discount_for(self, lines):
        eligible = sum((line.amount for line in lines if self.applies_to(line)), Decimal('0'))
        return to_money(eligible * self.percent / 100)


class FixedCoupon:
    def __init__(self, code, amount, category=None):
        self.code = code
        self.amount = to_money(amount)
        self.category = category

    def applies_to(self, line):
        return self.category is None or line.category == self.category

    def discount_for(self, lines):
        eligible = sum((line.amount for line in lines if self.applies_to(line)), Decimal('0'))
        return min(self.amount, eligible)


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

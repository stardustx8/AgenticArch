from dataclasses import dataclass
from decimal import Decimal

from .money import to_money

ZERO = Decimal('0')


@dataclass
class PriceBreakdown:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal


def price_lines(lines, coupons, region, tax_table):
    subtotal = sum((line.amount for line in lines), ZERO)
    tax = sum((to_money(line.amount * tax_table.rate_for(region, line.category)) for line in lines), ZERO)
    discount = sum((coupon.discount_for(lines) for coupon in coupons), ZERO)
    discount = min(discount, subtotal)
    return PriceBreakdown(
        subtotal=to_money(subtotal),
        discount=to_money(discount),
        tax=to_money(tax),
        total=to_money(subtotal - discount + tax),
    )

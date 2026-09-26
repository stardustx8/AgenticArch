from dataclasses import dataclass, field
from decimal import Decimal

from .money import to_money

ZERO = Decimal('0')


@dataclass
class PriceBreakdown:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    line_taxes: dict = field(default_factory=dict)


def price_lines(lines, coupons, region, tax_table):
    '''Coupons (in the given order) reduce line amounts first, then tax is charged per line.'''
    amounts = [line.amount for line in lines]
    subtotal = sum(amounts, ZERO)
    for coupon in coupons:
        eligible = [i for i, line in enumerate(lines) if coupon.applies_to(line)]
        shares = coupon.allocate([amounts[i] for i in eligible])
        for i, share in zip(eligible, shares):
            amounts[i] -= share
    taxes = [
        to_money(amount * tax_table.rate_for(region, line.category))
        for line, amount in zip(lines, amounts)
    ]
    line_taxes = {}
    for line, line_tax in zip(lines, taxes):
        line_taxes[line.sku] = line_taxes.get(line.sku, ZERO) + line_tax
    tax = sum(taxes, ZERO)
    discounted = sum(amounts, ZERO)
    return PriceBreakdown(
        subtotal=to_money(subtotal),
        discount=to_money(subtotal - discounted),
        tax=to_money(tax),
        total=to_money(discounted + tax),
        line_taxes=line_taxes,
    )

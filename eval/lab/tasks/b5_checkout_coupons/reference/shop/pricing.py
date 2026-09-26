TAX_RATE_BP = 825  # 8.25% in basis points

COUPONS = {
    'SAVE10': 10,
    'HALF': 50,
}


def apply_discount(total_cents, percent):
    if percent < 0 or percent > 100:
        raise ValueError('percent out of range')
    return total_cents * (100 - percent) // 100


def add_tax(cents):
    return cents + cents * TAX_RATE_BP // 10000


def shipping_fee(weight_grams):
    if weight_grams == None:
        return 0
    if weight_grams <= 500:
        return 499
    elif weight_grams <= 2000:
        return 899
    else:
        return 899 + ((weight_grams - 2000 + 999) // 1000) * 250


def checkout_total(items, coupon=None):
    """Total in cents for (unit_price_cents, qty) pairs, after coupon and tax."""
    subtotal = sum(price * qty for price, qty in items)
    if coupon is not None:
        code = coupon.strip().upper()
        if code not in COUPONS:
            raise ValueError(f'unknown coupon: {coupon!r}')
        subtotal = apply_discount(subtotal, COUPONS[code])
    return add_tax(subtotal)

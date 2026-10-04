from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def parse_amount(text):
    # '12.34' -> 1234 cents; rounds half away from zero past two decimals.
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise ValueError('not an amount: %r' % (text,)) from None
    if not value.is_finite():
        raise ValueError('not an amount: %r' % (text,))
    return int((value * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def format_cents(cents):
    sign = '-' if cents < 0 else ''
    whole, part = divmod(abs(cents), 100)
    return '%s%d.%02d' % (sign, whole, part)

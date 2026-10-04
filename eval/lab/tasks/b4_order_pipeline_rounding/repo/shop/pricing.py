from decimal import Decimal

CENT = Decimal('0.01')


def unit_price_for(product, quantity):
    '''Unit price after volume breaks: the break with the highest min_qty <= quantity wins.'''
    price = product.unit_price
    best = 0
    for min_qty, break_price in product.price_breaks:
        if best < min_qty <= quantity:
            best, price = min_qty, break_price
    return price


def price_line(line, catalog):
    product = catalog.get(line.sku)
    line.unit_price = unit_price_for(product, line.quantity)
    line.tax_category = product.tax_category
    line.line_total = (line.unit_price * line.quantity).quantize(CENT)
    return line

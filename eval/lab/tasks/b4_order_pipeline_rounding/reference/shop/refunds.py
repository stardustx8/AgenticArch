from .money import quantize_money


def refund_amount(order, sku, quantity):
    '''Amount to pay back when ``quantity`` units of ``sku`` are returned.

    Covers the units' share of the net line amount plus their share of the tax.
    '''
    line = next((l for l in order.lines if l.sku == sku), None)
    if line is None:
        raise KeyError(f'{sku!r} not in order {order.order_id}')
    if not 0 < quantity <= line.quantity:
        raise ValueError('invalid refund quantity')
    per_unit = (line.net + line.tax) / line.quantity
    return quantize_money(per_unit * quantity)

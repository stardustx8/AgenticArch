from .models import Order, OrderLine
from .pricing import price_line
from .tax import apply_tax


def checkout(order_id, region, items, catalog, coupon=None, repository=None):
    '''Price, discount and tax an order; ``items`` is a list of (sku, quantity).'''
    order = Order(order_id=order_id, region=region, coupon=coupon)
    for sku, quantity in items:
        if quantity <= 0:
            raise ValueError(f'quantity for {sku!r} must be positive')
        order.lines.append(price_line(OrderLine(sku=sku, quantity=quantity), catalog))
    if coupon is not None:
        coupon.apply(order.lines)
    apply_tax(order.lines, region)
    if repository is not None:
        repository.save(order)
    return order

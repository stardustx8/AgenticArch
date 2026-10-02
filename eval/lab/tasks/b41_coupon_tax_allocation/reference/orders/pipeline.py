from .models import LineItem, OrderRecord
from .pricing import price_lines


class EmptyOrder(ValueError):
    pass


class OrderService:
    def __init__(self, catalog, coupons, tax_table, store):
        self.catalog = catalog
        self.coupons = coupons
        self.tax_table = tax_table
        self.store = store

    def _build_lines(self, items):
        merged = {}
        for sku, quantity in items:
            if quantity <= 0:
                raise ValueError(f'quantity for {sku} must be positive')
            merged[sku] = merged.get(sku, 0) + quantity
        if not merged:
            raise EmptyOrder('an order needs at least one line')
        lines = []
        for sku, quantity in merged.items():
            product = self.catalog.get(sku)
            lines.append(LineItem(sku, product.price, quantity, product.category))
        return lines

    def _resolve_coupons(self, codes):
        coupons = []
        for code in codes:
            coupon = self.coupons.get(code)
            if coupon not in coupons:
                coupons.append(coupon)
        return coupons

    def place_order(self, order_id, customer_id, region, items, coupon_codes=()):
        lines = self._build_lines(items)
        coupons = self._resolve_coupons(coupon_codes)
        breakdown = price_lines(lines, coupons, region, self.tax_table)
        record = OrderRecord(
            order_id=order_id,
            customer_id=customer_id,
            region=region,
            coupons=[coupon.code for coupon in coupons],
            lines=lines,
            subtotal=breakdown.subtotal,
            discount=breakdown.discount,
            tax=breakdown.tax,
            total=breakdown.total,
            line_taxes=breakdown.line_taxes,
        )
        self.store.save(record)
        return record

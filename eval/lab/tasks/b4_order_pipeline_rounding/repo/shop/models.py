from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal = Decimal('0')
    tax_category: str = 'standard'
    line_total: Decimal = Decimal('0')  # before discount
    discount: Decimal = Decimal('0')
    tax: Decimal = Decimal('0')

    @property
    def net(self):
        return self.line_total - self.discount


@dataclass
class Order:
    order_id: str
    region: str
    lines: list = field(default_factory=list)
    coupon: object = None

    @property
    def subtotal(self):
        return sum((l.line_total for l in self.lines), Decimal('0'))

    @property
    def discount_total(self):
        return sum((l.discount for l in self.lines), Decimal('0'))

    @property
    def tax_total(self):
        return sum((l.tax for l in self.lines), Decimal('0'))

    @property
    def total(self):
        return self.subtotal - self.discount_total + self.tax_total

from dataclasses import dataclass, field
from decimal import Decimal

from .money import to_money


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price: Decimal
    category: str


@dataclass(frozen=True)
class LineItem:
    sku: str
    unit_price: Decimal
    quantity: int
    category: str

    @property
    def amount(self):
        return to_money(self.unit_price * self.quantity)

    def to_dict(self):
        return {
            'sku': self.sku,
            'unit_price': str(self.unit_price),
            'quantity': self.quantity,
            'category': self.category,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data['sku'], Decimal(data['unit_price']), int(data['quantity']), data['category'])


@dataclass
class OrderRecord:
    order_id: str
    customer_id: str
    region: str
    coupons: list
    lines: list
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    status: str = 'placed'
    line_taxes: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            'order_id': self.order_id,
            'customer_id': self.customer_id,
            'region': self.region,
            'coupons': list(self.coupons),
            'lines': [line.to_dict() for line in self.lines],
            'subtotal': str(self.subtotal),
            'discount': str(self.discount),
            'tax': str(self.tax),
            'total': str(self.total),
            'status': self.status,
            'line_taxes': {sku: str(amount) for sku, amount in self.line_taxes.items()},
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            order_id=data['order_id'],
            customer_id=data['customer_id'],
            region=data['region'],
            coupons=list(data['coupons']),
            lines=[LineItem.from_dict(item) for item in data['lines']],
            subtotal=Decimal(data['subtotal']),
            discount=Decimal(data['discount']),
            tax=Decimal(data['tax']),
            total=Decimal(data['total']),
            status=data['status'],
            # orders saved before per-line tax was tracked have no line_taxes
            line_taxes={sku: Decimal(amount) for sku, amount in data.get('line_taxes', {}).items()},
        )

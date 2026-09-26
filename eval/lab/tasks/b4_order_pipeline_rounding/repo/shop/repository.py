import json
from decimal import Decimal
from pathlib import Path

from .discounts import coupon_from_dict, coupon_to_dict
from .models import Order, OrderLine

_DECIMAL_FIELDS = ('unit_price', 'line_total', 'discount', 'tax')


class OrderRepository:
    '''Stores each order as ``<order_id>.json`` in a directory.'''

    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, order_id):
        return self.directory / f'{order_id}.json'

    def save(self, order):
        data = {
            'order_id': order.order_id,
            'region': order.region,
            'coupon': coupon_to_dict(order.coupon),
            'lines': [
                {'sku': l.sku, 'quantity': l.quantity, 'tax_category': l.tax_category,
                 **{f: str(getattr(l, f)) for f in _DECIMAL_FIELDS}}
                for l in order.lines
            ],
        }
        self._path(order.order_id).write_text(json.dumps(data, indent=2))

    def load(self, order_id):
        data = json.loads(self._path(order_id).read_text())
        lines = [
            OrderLine(sku=raw['sku'], quantity=raw['quantity'], tax_category=raw['tax_category'],
                      **{f: Decimal(raw[f]) for f in _DECIMAL_FIELDS})
            for raw in data['lines']
        ]
        return Order(order_id=data['order_id'], region=data['region'], lines=lines,
                     coupon=coupon_from_dict(data['coupon']))

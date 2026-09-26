from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    unit_price: Decimal
    tax_category: str = 'standard'
    # ((min_qty, unit_price), ...) volume breaks
    price_breaks: tuple = ()


class Catalog:
    def __init__(self, products=()):
        self._products = {p.sku: p for p in products}

    def add(self, product):
        self._products[product.sku] = product

    def get(self, sku):
        try:
            return self._products[sku]
        except KeyError:
            raise KeyError(f'unknown sku {sku!r}') from None

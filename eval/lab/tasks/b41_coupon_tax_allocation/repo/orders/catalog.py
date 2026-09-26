from decimal import Decimal

from .models import Product


class UnknownProduct(KeyError):
    pass


class Catalog:
    def __init__(self, products=()):
        self._products = {}
        for product in products:
            self.add(product)

    def add(self, product):
        self._products[product.sku] = product

    def get(self, sku):
        try:
            return self._products[sku]
        except KeyError:
            raise UnknownProduct(sku) from None


def default_catalog():
    return Catalog([
        Product('BOOK-1', 'Paperback novel', Decimal('12.99'), 'books'),
        Product('MUG-1', 'Coffee mug', Decimal('8.50'), 'kitchen'),
        Product('TEA-1', 'Green tea 100g', Decimal('6.25'), 'grocery'),
        Product('LAMP-1', 'Desk lamp', Decimal('34.00'), 'home'),
    ])

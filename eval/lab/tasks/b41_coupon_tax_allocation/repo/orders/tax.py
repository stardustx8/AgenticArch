from decimal import Decimal


class UnknownRegion(KeyError):
    pass


class TaxTable:
    '''Sales tax rate per region, with per-region exempt categories.'''

    def __init__(self, rates, exempt=None):
        self._rates = dict(rates)
        self._exempt = {region: set(cats) for region, cats in (exempt or {}).items()}

    def rate_for(self, region, category):
        if region not in self._rates:
            raise UnknownRegion(region)
        if category in self._exempt.get(region, ()):
            return Decimal('0')
        return self._rates[region]


def default_tax_table():
    return TaxTable(
        {'CA': Decimal('0.0725'), 'NY': Decimal('0.08875'), 'OR': Decimal('0')},
        exempt={'CA': {'grocery'}, 'NY': {'grocery', 'books'}},
    )

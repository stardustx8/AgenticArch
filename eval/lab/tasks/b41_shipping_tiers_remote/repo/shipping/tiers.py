from .rates import EXTRA_PER_KG, TIERS


class Overweight(ValueError):
    pass


class UnknownService(KeyError):
    pass


class TierTable:
    def __init__(self, tiers, extra_per_kg):
        self.tiers = list(tiers)
        self.extra_per_kg = list(extra_per_kg)

    @property
    def top_limit(self):
        return self.tiers[-1][0]

    def base_price(self, grams, zone):
        '''Base price in cents for a billable weight in grams.'''
        for limit, prices in self.tiers:
            if grams < limit:
                return prices[zone - 1]
        raise Overweight(f'{grams} g is over the {self.top_limit} g limit')


def table_for(service):
    try:
        tiers = TIERS[service]
    except KeyError:
        raise UnknownService(service) from None
    return TierTable(tiers, EXTRA_PER_KG[service])

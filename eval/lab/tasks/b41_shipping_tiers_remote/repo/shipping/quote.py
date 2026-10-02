from dataclasses import dataclass

from .dimensional import dim_weight_grams
from .rates import FUEL_BASIS_POINTS, RESIDENTIAL_CENTS
from .tiers import table_for
from .zones import zone_for


@dataclass(frozen=True)
class Quote:
    service: str
    zone: int
    billable_grams: int
    base: int
    residential: int
    fuel: int
    total: int


def fuel_for(amount_cents, basis_points):
    '''Fuel surcharge in cents, rounded half up.'''
    return (amount_cents * basis_points + 5000) // 10000


def quote_package(package, origin, destination, service='standard', residential=False):
    '''Price one package. All amounts are integer cents.'''
    table = table_for(service)
    zone = zone_for(origin, destination)
    billable = max(package.actual_grams(), dim_weight_grams(package.dims, package.dim_unit))
    base = table.base_price(billable, zone)
    residential_fee = RESIDENTIAL_CENTS if residential else 0
    surcharged = base + residential_fee
    fuel = fuel_for(surcharged, FUEL_BASIS_POINTS[service])
    return Quote(
        service=service,
        zone=zone,
        billable_grams=billable,
        base=base,
        residential=residential_fee,
        fuel=fuel,
        total=surcharged + fuel,
    )

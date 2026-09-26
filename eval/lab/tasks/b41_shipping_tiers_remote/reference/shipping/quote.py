from dataclasses import dataclass

from .dimensional import dim_weight_grams
from .rates import FUEL_BASIS_POINTS, MAX_ACTUAL_GRAMS, REMOTE_SURCHARGE_CENTS, RESIDENTIAL_CENTS
from .tiers import Overweight, table_for
from .zones import is_remote, zone_for


@dataclass(frozen=True)
class Quote:
    service: str
    zone: int
    billable_grams: int
    base: int
    residential: int
    fuel: int
    total: int
    remote: int = 0


def fuel_for(amount_cents, basis_points):
    '''Fuel surcharge in cents, rounded half up.'''
    return (amount_cents * basis_points + 5000) // 10000


def quote_package(package, origin, destination, service='standard', residential=False):
    '''Price one package. All amounts are integer cents.'''
    table = table_for(service)
    zone = zone_for(origin, destination)
    actual = package.actual_grams()
    if actual > MAX_ACTUAL_GRAMS:
        raise Overweight(f'{actual} g is over the {MAX_ACTUAL_GRAMS} g limit')
    billable = max(actual, dim_weight_grams(package.dims, package.dim_unit))
    base = table.base_price(billable, zone)
    residential_fee = RESIDENTIAL_CENTS if residential else 0
    remote_fee = REMOTE_SURCHARGE_CENTS if is_remote(destination) else 0
    surcharged = base + residential_fee + remote_fee
    fuel = fuel_for(surcharged, FUEL_BASIS_POINTS[service])
    return Quote(
        service=service,
        zone=zone,
        billable_grams=billable,
        base=base,
        residential=residential_fee,
        fuel=fuel,
        total=surcharged + fuel,
        remote=remote_fee,
    )

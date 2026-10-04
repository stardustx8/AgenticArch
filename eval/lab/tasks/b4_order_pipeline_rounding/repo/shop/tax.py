from decimal import Decimal

from .money import quantize_money

RATES = {
    'DE': {'standard': Decimal('0.19'), 'food': Decimal('0.07'), 'exempt': Decimal('0')},
    'NL': {'standard': Decimal('0.21'), 'food': Decimal('0.09'), 'exempt': Decimal('0')},
}


def rate_for(region, category):
    try:
        return RATES[region][category]
    except KeyError:
        raise KeyError(f'no tax rate for {region}/{category}') from None


def apply_tax(lines, region):
    '''Tax each line on its net (discounted) amount.'''
    for line in lines:
        line.tax = quantize_money(line.net * rate_for(region, line.tax_category))

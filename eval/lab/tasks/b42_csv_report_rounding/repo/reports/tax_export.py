"""VAT export for the tax authority.

The authority's filing rules require net and VAT amounts to be computed per
transaction and rounded to the cent with round-half-even (banker's rounding).
This must stay that way even if internal reports round differently.
"""
from decimal import Decimal

from .money import round_cents

VAT_RATES = {'books': Decimal('0.05'), 'food': Decimal('0.10'), 'services': Decimal('0.20')}


def vat_lines(transactions, rates):
    """One (date, category, net, vat) tuple per transaction, in the rates' base currency."""
    lines = []
    for t in transactions:
        category = t.category.strip()
        rate = VAT_RATES.get(category.lower(), Decimal(0))
        net = rates.convert(t.amount, t.currency)
        lines.append((t.date.isoformat(), category, round_cents(net), round_cents(net * rate)))
    return lines


def export_csv(transactions, rates):
    out = ['date,category,net,vat']
    for day, category, net, vat in vat_lines(transactions, rates):
        out.append(f'{day},{category},{net},{vat}')
    return '\n'.join(out) + '\n'

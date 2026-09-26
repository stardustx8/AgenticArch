from allocate import allocate
from money import format_cents, parse_amount


def split_invoice(total, people):
    # people maps name -> weight; returns name -> formatted share, in the same order.
    names = list(people)
    shares = allocate(parse_amount(total), [people[name] for name in names])
    return {name: format_cents(share) for name, share in zip(names, shares)}

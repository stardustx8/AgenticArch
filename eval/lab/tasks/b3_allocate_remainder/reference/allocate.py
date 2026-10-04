from fractions import Fraction


def allocate(total_cents, weights, unit=1):
    # Split an integer number of cents in proportion to weights (largest remainder):
    # every share is floored to a multiple of `unit`, then the leftover units go out
    # one at a time to the largest remainders, earlier entries winning ties.
    # Negative totals mirror the positive split exactly.
    if unit < 1:
        raise ValueError('unit must be a positive number of cents')
    if total_cents % unit:
        raise ValueError('%d is not a multiple of %d' % (total_cents, unit))
    weights = [Fraction(w) for w in weights]
    if any(w < 0 for w in weights):
        raise ValueError('weights must not be negative')
    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError('weights must add up to a positive number')
    if total_cents < 0:
        return [-share for share in allocate(-total_cents, weights, unit)]
    units = total_cents // unit
    exact = [units * w / weight_sum for w in weights]
    counts = [int(x) for x in exact]
    leftover = units - sum(counts)
    by_remainder = sorted(range(len(exact)), key=lambda i: (counts[i] - exact[i], i))
    for i in by_remainder[:leftover]:
        counts[i] += 1
    return [count * unit for count in counts]

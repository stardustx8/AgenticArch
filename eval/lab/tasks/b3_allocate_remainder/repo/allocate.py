def allocate(total_cents, weights):
    # Split an integer number of cents in proportion to weights.
    weights = list(weights)
    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError('weights must add up to a positive number')
    shares = [total_cents * w // weight_sum for w in weights]
    shares[-1] += total_cents - sum(shares)
    return shares

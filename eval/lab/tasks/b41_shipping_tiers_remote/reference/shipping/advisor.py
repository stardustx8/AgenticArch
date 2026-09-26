from .tiers import table_for


def weight_headroom(grams, service='standard'):
    '''How many more grams a parcel of this billable weight can take before it costs more.

    Tier limits are inclusive. None when the parcel is already past the top tier.'''
    for limit, _prices in table_for(service).tiers:
        if grams <= limit:
            return limit - grams
    return None

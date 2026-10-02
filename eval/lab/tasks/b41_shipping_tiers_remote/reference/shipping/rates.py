'''Rate card. Prices are integer cents; weight limits are grams.'''

# (upper weight limit, inclusive, [price for zone 1..5])
TIERS = {
    'standard': [
        (500, [520, 610, 700, 820, 990]),
        (1000, [640, 750, 880, 1010, 1240]),
        (2000, [810, 960, 1130, 1320, 1600]),
        (5000, [1150, 1380, 1620, 1900, 2350]),
        (10000, [1690, 2040, 2400, 2830, 3500]),
        (20000, [2600, 3150, 3700, 4380, 5400]),
    ],
    'express': [
        (500, [990, 1150, 1320, 1540, 1860]),
        (1000, [1210, 1400, 1620, 1880, 2290]),
        (2000, [1540, 1790, 2080, 2420, 2950]),
        (5000, [2190, 2560, 2980, 3480, 4250]),
        (10000, [3210, 3760, 4390, 5130, 6300]),
        (20000, [4940, 5800, 6780, 7920, 9750]),
    ],
}

# Price per started kg of billable weight above the top tier, zone 1..5.
EXTRA_PER_KG = {
    'standard': [95, 115, 135, 160, 210],
    'express': [180, 210, 250, 290, 380],
}

# Parcels whose actual weight is above this are refused.
MAX_ACTUAL_GRAMS = 70000

RESIDENTIAL_CENTS = 350

# Fuel surcharge in basis points (850 = 8.5%), charged on the base price plus surcharges.
FUEL_BASIS_POINTS = {'standard': 850, 'express': 1150}

# Remote delivery areas (Alaska, Hawaii) by destination ZIP prefix: always zone 5, flat surcharge.
REMOTE_PREFIXES = ('995', '996', '997', '998', '999', '967', '968')
REMOTE_SURCHARGE_CENTS = 1200

import math

from .units import to_cm

# cm^3 per kg
DIM_DIVISOR = 5000


def dim_weight_grams(dims, unit='cm'):
    '''Volumetric weight in whole grams (rounded up); 0 when no dimensions are known.'''
    if dims is None:
        return 0
    length, width, height = (to_cm(value, unit) for value in dims)
    return math.ceil(length * width * height * 1000 / DIM_DIVISOR)

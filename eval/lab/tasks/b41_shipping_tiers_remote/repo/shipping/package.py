from dataclasses import dataclass

from .units import to_grams


@dataclass(frozen=True)
class Package:
    weight: object
    weight_unit: str = 'kg'
    dims: tuple = None
    dim_unit: str = 'cm'

    def actual_grams(self):
        return to_grams(self.weight, self.weight_unit)

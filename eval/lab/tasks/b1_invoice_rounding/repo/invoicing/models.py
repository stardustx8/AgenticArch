from dataclasses import dataclass


@dataclass
class LineItem:
    description: str
    unit_price: float
    quantity: int
    tax_rate: float = 0.0  # 0.2 means 20%

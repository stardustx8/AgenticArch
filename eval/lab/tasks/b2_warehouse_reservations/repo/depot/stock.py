"""Low-level on-hand stock ledger."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import OutOfStock


def positive_qty(qty: object) -> int:
    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
        raise ValueError(f"quantity must be a positive integer, got {qty!r}")
    return qty


@dataclass(frozen=True)
class Movement:
    kind: str  # "receive" or "ship"
    sku: str
    qty: int
    at: float


class StockLedger:
    """Physical units on hand per SKU, plus the history of how they got there."""

    def __init__(self) -> None:
        self._on_hand: dict[str, int] = {}
        self._movements: list[Movement] = []

    def on_hand(self, sku: str) -> int:
        return self._on_hand.get(sku, 0)

    def receive(self, sku: str, qty: int, at: float) -> int:
        qty = positive_qty(qty)
        self._on_hand[sku] = self.on_hand(sku) + qty
        self._movements.append(Movement("receive", sku, qty, at))
        return self._on_hand[sku]

    def ship(self, sku: str, qty: int, at: float) -> int:
        qty = positive_qty(qty)
        have = self.on_hand(sku)
        if qty > have:
            raise OutOfStock(sku, qty, have)
        self._on_hand[sku] = have - qty
        self._movements.append(Movement("ship", sku, qty, at))
        return self._on_hand[sku]

    def movements(self, sku: str | None = None) -> list[Movement]:
        if sku is None:
            return list(self._movements)
        return [m for m in self._movements if m.sku == sku]

    def skus(self) -> list[str]:
        return sorted(self._on_hand)

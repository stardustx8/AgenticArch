"""Warehouse facade: the API the order service talks to."""

from __future__ import annotations

from .clock import Clock
from .stock import StockLedger


class Warehouse:
    """Single-site warehouse. All movements are stamped with ``clock.now()``."""

    def __init__(self, clock: Clock, ledger: StockLedger | None = None) -> None:
        self._clock = clock
        self._ledger = ledger if ledger is not None else StockLedger()

    @property
    def ledger(self) -> StockLedger:
        return self._ledger

    def receive(self, sku: str, qty: int) -> None:
        self._ledger.receive(sku, qty, at=self._clock.now())

    def ship(self, sku: str, qty: int) -> None:
        self._ledger.ship(sku, qty, at=self._clock.now())

    def on_hand(self, sku: str) -> int:
        return self._ledger.on_hand(sku)

    def available(self, sku: str) -> int:
        """Units that can still be promised to a new order."""
        return self.on_hand(sku)

    def stock_report(self) -> dict[str, tuple[int, int]]:
        """``{sku: (on_hand, available)}`` for every SKU ever received."""
        return {
            sku: (self.on_hand(sku), self.available(sku))
            for sku in self._ledger.skus()
        }

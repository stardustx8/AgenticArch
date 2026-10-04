"""Warehouse facade: the API the order service talks to."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .clock import Clock
from .errors import OutOfStock, ReservationError, ReservationExpired
from .stock import StockLedger, positive_qty


@dataclass(frozen=True)
class _Hold:
    lines: dict[str, int]
    expires_at: float


class Warehouse:
    """Single-site warehouse. All movements are stamped with ``clock.now()``."""

    def __init__(self, clock: Clock, ledger: StockLedger | None = None) -> None:
        self._clock = clock
        self._ledger = ledger if ledger is not None else StockLedger()
        self._holds: dict[str, _Hold] = {}

    @property
    def ledger(self) -> StockLedger:
        return self._ledger

    def receive(self, sku: str, qty: int) -> None:
        self._ledger.receive(sku, qty, at=self._clock.now())

    def ship(self, sku: str, qty: int) -> None:
        qty = positive_qty(qty)
        free = self.available(sku)
        if qty > free:
            raise OutOfStock(sku, qty, free)
        self._ledger.ship(sku, qty, at=self._clock.now())

    def on_hand(self, sku: str) -> int:
        return self._ledger.on_hand(sku)

    def available(self, sku: str) -> int:
        """Units that can still be promised to a new order."""
        return self.on_hand(sku) - self.held(sku)

    def held(self, sku: str) -> int:
        """Units of ``sku`` tied up in active (unexpired) reservations."""
        now = self._clock.now()
        return sum(
            hold.lines.get(sku, 0)
            for hold in self._holds.values()
            if now < hold.expires_at
        )

    def reserve(self, order_id: str, lines: Mapping[str, int], ttl: float) -> None:
        """Hold every line of an order for ``ttl`` seconds, or nothing at all."""
        if ttl <= 0:
            raise ValueError(f"ttl must be positive, got {ttl!r}")
        wanted = {sku: positive_qty(qty) for sku, qty in lines.items()}
        now = self._clock.now()
        existing = self._holds.get(order_id)
        if existing is not None and now < existing.expires_at:
            raise ReservationError(f"order {order_id!r} already has an active hold")
        for sku, qty in wanted.items():
            free = self.available(sku)
            if qty > free:
                raise OutOfStock(sku, qty, free)
        self._holds[order_id] = _Hold(wanted, now + ttl)

    def commit(self, order_id: str) -> None:
        """Turn a hold into a real shipment."""
        hold = self._pop_hold(order_id)
        now = self._clock.now()
        if now >= hold.expires_at:
            raise ReservationExpired(
                f"hold for order {order_id!r} expired at {hold.expires_at}"
            )
        for sku, qty in hold.lines.items():
            self._ledger.ship(sku, qty, at=now)

    def release(self, order_id: str) -> None:
        """Give a held order's stock back."""
        self._pop_hold(order_id)

    def stock_report(self) -> dict[str, tuple[int, int]]:
        """``{sku: (on_hand, available)}`` for every SKU ever received."""
        return {
            sku: (self.on_hand(sku), self.available(sku))
            for sku in self._ledger.skus()
        }

    def _pop_hold(self, order_id: str) -> _Hold:
        try:
            return self._holds.pop(order_id)
        except KeyError:
            raise ReservationError(f"no reservation for order {order_id!r}") from None

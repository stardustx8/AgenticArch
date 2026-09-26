"""Per-SKU stock levels with an audit trail."""

from __future__ import annotations

from collections.abc import Mapping

from .audit import AuditLog


def _check_qty(qty: object) -> int:
    # bool is an int subclass, but add_stock("X", True) is always a bug.
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise ValueError(f"quantity must be an int, got {qty!r}")
    if qty <= 0:
        raise ValueError(f"quantity must be positive, got {qty}")
    return qty


class Inventory:
    """On-hand quantities keyed by SKU.

    Every successful movement is appended to ``audit``.
    """

    def __init__(self, audit: AuditLog | None = None) -> None:
        self._levels: dict[str, int] = {}
        self.audit = audit if audit is not None else AuditLog()

    def add_stock(self, sku: str, qty: int) -> int:
        qty = _check_qty(qty)
        level = self._levels.get(sku, 0) + qty
        self._levels[sku] = level
        self.audit.record("add", sku, qty)
        return level

    def add_many(self, lines: Mapping[str, int]) -> None:
        """Book a delivery; every quantity is validated before anything is added."""
        checked = {sku: _check_qty(qty) for sku, qty in lines.items()}
        for sku, qty in checked.items():
            self.add_stock(sku, qty)

    def remove_stock(self, sku: str, qty: int) -> int:
        qty = _check_qty(qty)
        level = self._levels.get(sku, 0) - qty
        self._levels[sku] = level
        self.audit.record("remove", sku, qty)
        return level

    def quantity(self, sku: str) -> int:
        return self._levels.get(sku, 0)

    def skus(self) -> list[str]:
        return sorted(self._levels)

    def snapshot(self) -> dict[str, int]:
        return dict(self._levels)

    def total_units(self) -> int:
        return sum(self._levels.values())

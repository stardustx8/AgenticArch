"""In-memory audit trail of stock movements."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

ACTIONS = ("add", "remove")


@dataclass(frozen=True)
class AuditEntry:
    action: str
    sku: str
    qty: int


class AuditLog:
    """Append-only record of every stock movement."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, action: str, sku: str, qty: int) -> AuditEntry:
        if action not in ACTIONS:
            raise ValueError(f"unknown audit action {action!r}")
        entry = AuditEntry(action, sku, qty)
        self._entries.append(entry)
        return entry

    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def for_sku(self, sku: str) -> list[AuditEntry]:
        return [entry for entry in self._entries if entry.sku == sku]

    def net_change(self, sku: str) -> int:
        total = 0
        for entry in self.for_sku(sku):
            total += entry.qty if entry.action == "add" else -entry.qty
        return total

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[AuditEntry]:
        return iter(list(self._entries))

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    id: str
    src: str
    dst: str
    amount: int
    memo: str = ""

    def involves(self, account: str) -> bool:
        return account in (self.src, self.dst)


@dataclass
class Account:
    name: str
    balance: int = 0

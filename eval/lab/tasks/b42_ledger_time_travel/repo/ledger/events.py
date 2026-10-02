from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    account_id: str
    seq: int


@dataclass(frozen=True)
class AccountOpened(Event):
    owner: str


@dataclass(frozen=True)
class Deposited(Event):
    amount_cents: int


@dataclass(frozen=True)
class Withdrawn(Event):
    amount_cents: int


@dataclass(frozen=True)
class AccountClosed(Event):
    reason: str = ''

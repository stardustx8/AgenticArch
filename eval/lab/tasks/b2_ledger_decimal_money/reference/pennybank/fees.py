"""Monthly maintenance fees."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from .account import CENT, Account

Percent = Decimal | int | str


def monthly_fee(balance: Decimal, percent: Percent) -> Decimal:
    """Fee owed on *balance* at *percent*, rounded half-up to the cent."""
    rate = Decimal(str(percent))
    if rate < 0:
        raise ValueError(f"fee percent cannot be negative, got {percent}")
    return (balance * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)


def apply_monthly_fee(account: Account, percent: Percent) -> Decimal:
    """Withdraw the monthly fee from *account* and return it.

    Nothing is recorded when the fee rounds to zero.
    """
    fee = monthly_fee(account.balance(), percent)
    if fee > 0:
        account.withdraw(fee)
    return fee


def charge_all(accounts: Iterable[Account], percent: Percent) -> dict[str, Decimal]:
    """Apply the monthly fee to every account, keyed by owner."""
    return {account.owner: apply_monthly_fee(account, percent) for account in accounts}

"""Monthly maintenance fees."""

from __future__ import annotations

from typing import Iterable

from .account import Account


def monthly_fee(balance: float, percent: float) -> float:
    """Fee owed on *balance* at *percent*, rounded to the cent."""
    if percent < 0:
        raise ValueError(f"fee percent cannot be negative, got {percent}")
    return round(balance * percent / 100, 2)


def apply_monthly_fee(account: Account, percent: float) -> float:
    """Withdraw the monthly fee from *account* and return it.

    Nothing is recorded when the fee rounds to zero.
    """
    fee = monthly_fee(account.balance(), percent)
    if fee > 0:
        account.withdraw(fee)
    return fee


def charge_all(accounts: Iterable[Account], percent: float) -> dict[str, float]:
    """Apply the monthly fee to every account, keyed by owner."""
    return {account.owner: apply_monthly_fee(account, percent) for account in accounts}

from dataclasses import dataclass

from .projection import AccountState


@dataclass(frozen=True)
class Snapshot:
    account_id: str
    version: int
    state: AccountState


class SnapshotStore:
    """Keeps every snapshot taken, per account."""

    def __init__(self):
        self._by_account = {}

    def save(self, snapshot):
        self._by_account.setdefault(snapshot.account_id, []).append(snapshot)

    def latest(self, account_id):
        snaps = self._by_account.get(account_id)
        if not snaps:
            return None
        return max(snaps, key=lambda s: s.version)

    def latest_at_or_before(self, account_id, version):
        """The newest snapshot whose version is <= ``version``, or None."""
        candidates = [s for s in self._by_account.get(account_id, []) if s.version <= version]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.version)

    def all_for(self, account_id):
        return sorted(self._by_account.get(account_id, []), key=lambda s: s.version)

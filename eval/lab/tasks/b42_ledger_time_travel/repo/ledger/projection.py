from dataclasses import dataclass

from .events import AccountClosed, AccountOpened, Deposited, Withdrawn


@dataclass
class AccountState:
    account_id: str
    owner: str = ''
    balance_cents: int = 0
    status: str = 'missing'
    version: int = 0


def apply(state, event):
    """Apply one event to ``state`` in place and return it."""
    if isinstance(event, AccountOpened):
        state.owner = event.owner
        state.status = 'open'
    elif isinstance(event, Deposited):
        state.balance_cents += event.amount_cents
    elif isinstance(event, Withdrawn):
        state.balance_cents -= event.amount_cents
    elif isinstance(event, AccountClosed):
        state.status = 'closed'
    else:
        raise TypeError(f'unknown event type: {type(event).__name__}')
    state.version = event.seq
    return state


def project(account_id, events, initial=None):
    """Fold ``events`` into ``initial`` (or a blank state) and return the result."""
    state = initial if initial is not None else AccountState(account_id)
    for event in events:
        apply(state, event)
    return state

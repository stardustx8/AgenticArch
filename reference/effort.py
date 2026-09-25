"""Generation-boundary lease and effective-setting acknowledgement contract.

No harness or model calls. A host adapter must stop dispatch on any error; merely
logging an exception in a permissive extension callback does not enforce this gate.
"""
from __future__ import annotations
from dataclasses import dataclass
from uuid import uuid4

DURATIONS = {1, 2, 5, 10}
INVALIDATORS = {'new_input', 'tool_failure', 'model_change', 'manual_override',
                'scope_change', 'resume', 'policy_change', 'deployment_change'}


@dataclass(frozen=True)
class Lease:
    decision_id: str
    session_id: str
    model_id: str
    epoch: int
    effort: str
    start: int
    generations: int
    state_digest: str


class EffortGate:
    def __init__(self, session_id: str, model_id: str, allowed: tuple[str, ...]):
        if not session_id or not model_id or not allowed or len(set(allowed)) != len(allowed):
            raise ValueError('Explicit session, model and unique allowed efforts required')
        self.session_id, self.model_id, self.allowed = session_id, model_id, allowed
        self.epoch, self.next_generation = 0, 0
        self.pending: Lease | None = None
        self.active: Lease | None = None
        self.in_flight = False
        self.manual: str | None = None

    def propose(self, effort: str, generations: int, state_digest: str) -> Lease:
        if self.in_flight or self.pending:
            raise ValueError('Only one pending choice at a safe generation boundary')
        if effort not in self.allowed or type(generations) is not int or generations not in DURATIONS:
            raise ValueError('Unapproved effort or duration')
        if self.manual is not None and effort != self.manual:
            raise ValueError('Manual override takes precedence')
        if not isinstance(state_digest, str) or len(state_digest) != 64 or any(c not in '0123456789abcdef' for c in state_digest):
            raise ValueError('A decision-context digest is required')
        self.active = None  # Superseded before application; old effort must not leak through.
        self.pending = Lease(uuid4().hex, self.session_id, self.model_id, self.epoch,
                             effort, self.next_generation, generations, state_digest)
        return self.pending

    def acknowledge(self, lease: Lease, *, session_id: str, model_id: str,
                    effort: str, next_generation: int) -> None:
        valid = (isinstance(lease, Lease) and lease == self.pending and lease.epoch == self.epoch and
                 session_id == self.session_id and model_id == self.model_id and
                 effort == lease.effort and type(next_generation) is int and
                 next_generation == self.next_generation == lease.start and not self.in_flight)
        if not valid:
            self.pending = self.active = None
            raise ValueError('Not applied: stale acknowledgement, model substitution or effort clamp')
        self.active, self.pending = lease, None

    def begin(self) -> str:
        lease = self.active
        if (self.in_flight or self.pending or lease is None or lease.epoch != self.epoch or
                lease.model_id != self.model_id or
                not lease.start <= self.next_generation < lease.start + lease.generations):
            raise ValueError('Generation blocked until an effective effort is acknowledged')
        self.in_flight = True
        return lease.effort

    def finish(self, *, failed: bool = False) -> None:
        if not self.in_flight or type(failed) is not bool:
            raise ValueError('No matching generation or invalid result')
        self.in_flight = False
        self.next_generation += 1
        if failed:
            self.invalidate('tool_failure')

    def invalidate(self, reason: str, *, manual: str | None = None) -> None:
        if reason not in INVALIDATORS or (manual is not None and manual not in self.allowed):
            raise ValueError('Unknown invalidator or effort')
        if self.in_flight:
            raise ValueError('Queue invalidation until the in-flight generation ends or is cancelled')
        if reason == 'manual_override':
            self.manual = manual  # None is an explicit resume-automatic operation.
        self.epoch += 1
        self.pending = self.active = None

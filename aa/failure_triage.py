"""Failure triage for failed checks (prototype; not yet wired into the daemon).

Decides what the coordinator should do with a failed check instead of always sending
the worker back:
  1. rerun the failed check once            -> passes now: FLAKY (no worker retry)
  2. run it on the base commit (clean tree) -> fails there too: PRE_EXISTING (report, don't blame the worker)
  3. ask the local decider (SemIf)          -> environment with confidence >= threshold:
                                               ENVIRONMENT (pause + ping the owner)
  4. otherwise                              -> CODE (send back to the worker, as today)
Steps 1-2 are deterministic; only step 3 is a model judgement (eval/PROBES.md:
environment recall 100%, precision 83% at conf >= 0.5).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import checks as checks_mod

QUESTION = 'What caused this check failure?'
OPTIONS = {
    'code': 'A bug or error in the code under test.',
    'environment': 'A problem with the machine or setup, such as a missing dependency, a service that is not '
                   'running, permissions, credentials or configuration.',
    'flaky': 'An intermittent timing or network hiccup; rerunning would likely pass.',
}


@dataclass
class Verdict:
    check: str
    action: str          # FLAKY | PRE_EXISTING | ENVIRONMENT | CODE
    reason: str
    probs: dict | None = None


def _confidence(p: dict) -> float:
    v = sorted(p.values(), reverse=True)
    return v[0] - sum(v[1:]) / max(1, len(v) - 1)


def triage(failed: checks_mod.CheckRun, worktree: Path, run_on_base: Callable[[str], checks_mod.CheckRun],
           decider, *, min_confidence: float = 0.5, task_id: str | None = None) -> Verdict:
    rerun = checks_mod.run({failed.name: failed.command}, worktree)[0]
    if rerun.ok:
        return Verdict(failed.name, 'FLAKY', 'failed once, passed on immediate rerun')
    base = run_on_base(failed.command)
    if not base.ok and _same_failure(base.output, rerun.output):
        return Verdict(failed.name, 'PRE_EXISTING', 'fails the same way on the base commit')
    pick, probs, _ = decider.choose('failure_cause', task_id, f'$ {failed.command}\n{rerun.output[-4000:]}',
                                    QUESTION, OPTIONS)
    if pick == 'environment' and probs and _confidence(probs) >= min_confidence:
        return Verdict(failed.name, 'ENVIRONMENT', 'local decider: machine/setup problem', probs)
    return Verdict(failed.name, 'CODE', 'send back to the worker', probs)


def _same_failure(a: str, b: str) -> bool:
    """Cheap similarity: the last error-looking line matches."""
    def last_err(s: str) -> str:
        lines = [l.strip() for l in s.splitlines() if any(k in l for k in ('Error', 'FAIL', 'error', 'failed'))]
        return lines[-1] if lines else s.strip()[-200:]
    return last_err(a) == last_err(b)

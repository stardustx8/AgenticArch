"""Host contract for the native Codex checkpoint; not a patch or shell proxy.

The native host supplies apply_settings and capture_settings under its own sampling
lock. It must not sample until this function and EffortGate.begin both succeed.
"""
from reference.effort import EffortGate, Lease


def apply_checkpoint(gate: EffortGate, lease: Lease, *, apply_settings, capture_settings):
    if lease != gate.pending:
        raise ValueError('Stale native checkpoint')
    try:
        apply_settings(model_id=lease.model_id, effort=lease.effort)
        actual = capture_settings()
        gate.acknowledge(lease, session_id=actual['session_id'],
                         model_id=actual['model_id'], effort=actual['effort'],
                         next_generation=actual['next_generation'])
    except Exception:
        gate.invalidate('scope_change')
        raise
    return lease.decision_id

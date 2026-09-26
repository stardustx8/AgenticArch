"""Ex-ante gate records. This module never changes the selected pipeline.

Only explicitly listed pre-dispatch fields may enter a future routing model.
Runtime outcomes and hidden-test results are deliberately not arguments.
"""
from __future__ import annotations


def snapshot(request: str, tier: str | None, triage: dict, checks: dict,
             oracle_enabled: bool, race_enabled: bool, spec_enabled: bool) -> dict:
    paths = {p for p in triage.get('relevant_paths', []) if isinstance(p, str)}
    return {
        'schema_version': 1,
        'stage': 'before_quality_dispatch',
        'features': {
            'request_chars': len(request),
            'tier': tier,
            'n_paths': len(paths),
            'n_criteria': len(triage.get('acceptance_criteria') or []),
            'n_risks': len(triage.get('risks') or []),
            'testable': bool(triage.get('testable')),
            'n_checks': len(checks),
            'pro_category': bool(triage.get('pro_categories')),
        },
        'configured': {'oracle': bool(oracle_enabled), 'race': bool(race_enabled),
                       'spec': bool(spec_enabled)},
        'recommendation': 'abstain_unfitted',
        'applied': False,
    }


def replay_choice(record: dict, proposed: str | None, available: set[str], fallback: str) -> dict:
    """Replay *dispatch validation*, never an unobserved coding outcome.

    A current pinned/running choice takes priority. Otherwise revalidate a
    selector's proposed id against the current menu and use a named fallback.
    The original historical record is not modified.
    """
    pinned = record.get('pinned')
    running = record.get('running')
    preserved = running if running is not None else pinned
    if preserved is not None:
        return {'choice': preserved, 'source': 'preserved', 'outcome': None}
    if proposed in available:
        return {'choice': proposed, 'source': 'selector', 'outcome': None}
    if fallback not in available:
        return {'choice': None, 'source': 'blocked_no_fallback', 'outcome': None}
    return {'choice': fallback, 'source': 'fallback', 'outcome': None}

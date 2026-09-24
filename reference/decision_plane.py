"""Offline semantic-decision contracts. No inference, I/O, permissions or execution.

The caller must collect trusted context, authenticate its scoring adapter and enforce
capabilities. These helpers produce requests and advisory records, never actions.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

REQUIRED_CONTEXT = (
    'project_id', 'task_id', 'snapshot_digest', 'requirements_digest',
    'policy_digest', 'authorization_scope_digest', 'model_revision',
    'tokenizer_revision', 'backend', 'quantization', 'prompt_template_digest',
    'runtime_revision', 'scoring_mode', 'calibration_id',
)
INFLUENCES = frozenset({
    'rank_context', 'suggest_gap_review', 'suggest_retrieval',
    'suggest_diagnostic', 'suggest_objection_link', 'suggest_local_delta_review',
    'suggest_memory_link', 'rank_test_candidates', 'suggest_attention',
})


def canonical(value: Any) -> bytes:
    """Reject lossy/nonfinite input; allow only actual JSON types and string keys."""
    def check(item: Any) -> None:
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(k) is str for k in item):
            for child in item.values():
                check(child)
            return
        raise ValueError('Not canonical JSON: unsupported type or nonfinite value')
    check(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _text(value: Any) -> bool:
    return type(value) is str and bool(value.strip())


def _sha(value: Any) -> bool:
    return (_text(value) and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value))


def _unique_texts(items: Any, *, nonempty: bool = True) -> bool:
    return (type(items) is list and (not nonempty or bool(items)) and
            all(_text(x) for x in items) and len(set(items)) == len(items))


def validate_operator(operator: Mapping[str, Any]) -> None:
    canonical(dict(operator))
    if not _text(operator.get('id')) or type(operator.get('version')) is not int or operator['version'] < 1:
        raise ValueError('Invalid operator identity')
    if operator.get('mode') not in {'off', 'shadow', 'advisory'}:
        raise ValueError('Invalid mode')
    if not _text(operator.get('question')):
        raise ValueError('An atomic question is required')
    for field in ('projection', 'triggers'):
        if not _unique_texts(operator.get(field)):
            raise ValueError(f'Invalid {field}')
    if not _unique_texts(operator.get('depends_on'), nonempty=False):
        raise ValueError('Invalid dependencies')
    if operator.get('allowed_influence') not in INFLUENCES or operator.get('fallback') != 'coordinator':
        raise ValueError('Unknown advisory influence or fallback')
    options = operator.get('options')
    if type(options) is not list or not 2 <= len(options) <= 16:
        raise ValueError('The reference contract requires 2 to 16 options')
    if any(type(x) is not dict or set(x) != {'id', 'description'} or
           not _text(x['id']) or not _text(x['description']) for x in options):
        raise ValueError('Invalid option')
    ids = [x['id'] for x in options]
    if len(set(ids)) != len(ids) or 'insufficient' not in ids:
        raise ValueError('Distinct options and explicit insufficient are required')


def stages(operators: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    """Plan dependency levels, not a parallel-execution or freshness guarantee."""
    for operator in operators:
        validate_operator(operator)
    by_id = {op['id']: op for op in operators}
    if len(by_id) != len(operators):
        raise ValueError('Duplicate operator IDs')
    if any(set(op['depends_on']) - set(by_id) for op in operators):
        raise ValueError('Unknown prerequisite')
    pending = set(by_id)
    done: set[str] = set()
    result = []
    while pending:
        ready = sorted(k for k in pending if set(by_id[k]['depends_on']) <= done)
        if not ready:
            raise ValueError('Dependency cycle')
        result.append(ready)
        done.update(ready)
        pending.difference_update(ready)
    return result


def make_request(operator: Mapping[str, Any], state: Mapping[str, Any],
                 context: Mapping[str, Any], *, event: str) -> dict[str, Any]:
    """Project caller-supplied scoped state; hash the complete scoring contract.

    Does not read files, verify source freshness, or authorize exporting this state.
    """
    validate_operator(operator)
    if operator['mode'] == 'off' or event not in operator['triggers']:
        raise ValueError('Operator is disabled or not applicable to this event')
    if any(not _text(context.get(k)) for k in REQUIRED_CONTEXT):
        raise ValueError('Incomplete execution provenance')
    if any(not _sha(context[k]) for k in REQUIRED_CONTEXT if k.endswith('_digest')):
        raise ValueError('Invalid execution digest')
    maximum = context.get('max_options')
    if type(maximum) is not int or maximum < 2 or len(operator['options']) > maximum:
        raise ValueError('Option count exceeds the qualified backend limit')
    if any(k not in state for k in operator['projection']):
        raise ValueError('Missing projected evidence; do not fabricate a value')
    payload = {'schema_version': 1, 'event': event, 'operator': dict(operator),
               'state': {k: state[k] for k in operator['projection']},
               'context': dict(context)}
    # An isolated JSON snapshot prevents subsequent caller mutation changing identity.
    frozen = json.loads(canonical(payload))
    return {'request_id': digest(frozen), **frozen}


def request_is_intact(request: Mapping[str, Any]) -> bool:
    try:
        body = {k: v for k, v in request.items() if k != 'request_id'}
        return _sha(request.get('request_id')) and digest(body) == request['request_id']
    except (ValueError, TypeError):
        return False


def shared_state_groups(requests: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    """Group independent requests with EXACT matching state and context.

    Never run these groups before earlier dependency stages finish. The caller must
    enforce event deduplication, numerical equivalence, memory limits and scopes.
    """
    groups: dict[str, list[str]] = {}
    ids = [r.get('request_id') for r in requests]
    if any(not _text(x) for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('Missing/duplicate request identity')
    operator_ids = {r['operator']['id'] for r in requests}
    for req in requests:
        if not request_is_intact(req):
            raise ValueError('Changed request')
        if set(req['operator']['depends_on']) & operator_ids:
            raise ValueError('Dependent questions require a later stage')
        key = digest({'state': req['state'], 'context': req['context'], 'event': req['event']})
        groups.setdefault(key, []).append(req['request_id'])
    return list(groups.values())


@dataclass(frozen=True)
class Advice:
    status: str  # ADVISE, SHADOW, ABSTAIN, FALLBACK
    selected: str | None
    influence: str | None
    reason: str


def interpret(request: Mapping[str, Any], response: Mapping[str, Any], *,
              qualified: bool = False) -> Advice:
    """Reject malformed/stale replies; produce no executable action or permission.

    `qualified` must come from a trusted family-specific qualification record, not
    from model output. This reference does not implement that record's storage.
    """
    if not request_is_intact(request):
        return Advice('FALLBACK', None, None, 'changed_request')
    if response.get('request_id') != request['request_id']:
        return Advice('ABSTAIN', None, None, 'stale_or_wrong_request')
    op = request['operator']
    options = [x['id'] for x in op['options']]
    scores = response.get('scores')
    if type(scores) is not dict or set(scores) != set(options):
        return Advice('ABSTAIN', None, None, 'invalid_option_set')
    if any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1
           for v in scores.values()):
        return Advice('ABSTAIN', None, None, 'invalid_scores')
    if not math.isclose(sum(scores.values()), 1.0, abs_tol=1e-6):
        return Advice('ABSTAIN', None, None, 'unnormalized_scores')
    best = max(scores.values())
    winners = [k for k, v in scores.items() if abs(v - best) <= 1e-12]
    if len(winners) != 1:
        return Advice('ABSTAIN', None, None, 'tie')
    winner = winners[0]
    if response.get('selected') != winner:
        return Advice('ABSTAIN', None, None, 'selected_option_mismatch')
    if winner == 'insufficient':
        return Advice('ABSTAIN', winner, None, 'insufficient_evidence')
    if op['mode'] != 'advisory' or qualified is not True:
        return Advice('SHADOW', winner, None, 'not_qualified_for_influence')
    return Advice('ADVISE', winner, op['allowed_influence'], 'requires_controller_validation')

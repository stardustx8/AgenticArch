"""Pure reference rules for AgenticArch, requiring Python 3.11+.

The caller must provide authenticated transport observations and actual command
results. These functions cannot prove that a model ran, a command ran, or that a
boolean supplied by a caller is true. They intentionally perform no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


class Lane(str, Enum):
    LUNA_LOW = 'luna_low'
    LUNA_HIGH = 'luna_high'
    ASTRA_HIGH = 'astra_high'
    PRO_WEB = 'pro_web'


LANES = tuple(Lane)
FLOORS = dict(zip(('routine', 'bounded', 'medium_tough', 'tough'), LANES))
PRO_CATEGORIES = frozenset({
    'architecture', 'research', 'security_design', 'migration_design',
    'irreversible_change_design',
})
SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _digest(value: str) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def validate_lane(model_family: str, reasoning: str | None) -> Lane:
    """Validate legacy competence anchors, not the complete worker candidate set."""
    lookup = {
        ('GPT-6 Luna', 'low'): Lane.LUNA_LOW,
        ('GPT-6 Luna', 'high'): Lane.LUNA_HIGH,
        ('GPT-6 Astra', 'high'): Lane.ASTRA_HIGH,
        ('GPT-6 Pro', None): Lane.PRO_WEB,
    }
    try:
        return lookup[(model_family, reasoning)]
    except KeyError as exc:
        raise ValueError('Model/effort is not an allowed policy lane') from exc


def validate_policy(policy: Mapping[str, Any]) -> None:
    if type(policy.get('schema_version')) is not int or policy['schema_version'] != 2:
        raise ValueError('Unsupported policy schema')
    if set(policy.get('lanes', {})) != {lane.value for lane in LANES}:
        raise ValueError('Policy must declare exactly the four competence anchors')
    for name, spec in policy['lanes'].items():
        if validate_lane(spec['model_family'], spec['reasoning']).value != name:
            raise ValueError('Lane name does not match model/effort')
    pro = policy['lanes']['pro_web']
    if pro.get('transport') != 'chatgpt_web' or pro.get('skill') != 'prepare-sol-pro-architecture-review':
        raise ValueError('Pro must use prepare-sol-pro-architecture-review and ChatGPT web')
    if policy.get('complexity_floor') != {k: v.value for k, v in FLOORS.items()}:
        raise ValueError('Complexity floors must match the four-lane policy')
    if set(policy.get('mandatory_pro_categories', [])) != PRO_CATEGORIES:
        raise ValueError('Mandatory Pro categories must not be weakened')
    for key in ('max_passes_per_lane', 'max_coding_passes', 'max_no_progress_passes'):
        if type(policy.get(key)) is not int or policy[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    clm = policy.get('clm', {})
    if clm.get('mode') not in {'shadow', 'advisory'}:
        raise ValueError('Unsupported CLM mode')
    if (clm.get('local_only') is not True or
            clm.get('can_lower_floor') is not False or
            clm.get('can_authorize_completion') is not False):
        raise ValueError('CLM authority must remain bounded and local')
    if (policy.get('model_catalog') != 'config/model-routing.json' or
            policy.get('harness_profiles') != 'config/harness-profiles.json' or
            policy.get('subscription_only') is not True or policy.get('api_fallback') is not False):
        raise ValueError('Shared subscription-only routing is required')
    verification = policy.get('verification', {})
    if any(verification.get(k) is not True for k in (
        'nonempty_required_checks', 'same_snapshot_and_plan', 'all_observed_failures_block'
    )):
        raise ValueError('Verification guards cannot be disabled')
    debate = policy.get('debate', {})
    if (debate.get('review_repository_name') != 'GPT-Pro-Escalation' or
            set(debate.get('required_roles', [])) != {'pro', 'reviewer'} or
            debate.get('same_chat_for_pro') is not True or
            debate.get('matching_solution_digests') is not True or
            debate.get('on_budget_exhausted') != 'PAUSED'):
        raise ValueError('Invalid debate policy')
    if (set(debate.get('reviewer_identities', [])) != {'claude-fable-5-1', 'claude-opus-5-5'} or
            debate.get('participant_bound_approvals') is not True):
        raise ValueError('Exact selected Claude participant must bind approvals')
    if debate.get('skill') != 'fable-adversarial-review':
        raise ValueError('The exact Fable skill identifier is required')
    transport = policy.get('pro_transport', {})
    if (transport.get('default') != 'manual' or
            any(transport.get(key) is not True for key in (
                'automatic_requires_permitted_capability', 'no_restriction_bypass',
                'no_silent_model_substitution'))):
        raise ValueError('Pro transport must be manual-first and permission-gated')
    for key in ('max_rounds_per_run', 'max_nonprogress_rounds'):
        if type(debate.get(key)) is not int or debate[key] < 1:
            raise ValueError('Debate budgets must be positive integers')


@dataclass(frozen=True)
class Routing:
    lane: Lane
    assessment_only: bool


def route(complexity: str, categories: Sequence[str] = (), *,
          risk_assessed: bool = True, current: Lane | None = None,
          advice: Lane | None = None) -> Routing:
    """Advice passed here must already be validated and advisory mode enabled."""
    if complexity not in FLOORS:
        raise ValueError('Unknown complexity; do not silently interpret it as routine')
    if type(risk_assessed) is not bool:
        raise ValueError('risk_assessed must be boolean')
    if set(categories) - PRO_CATEGORIES:
        raise ValueError('Unknown category requires explicit assessment')
    floor = FLOORS[complexity]
    if categories:
        floor = Lane.PRO_WEB
    elif not risk_assessed:
        floor = LANES[max(LANES.index(floor), LANES.index(Lane.ASTRA_HIGH))]
    candidates = [floor]
    for candidate in (current, advice):
        if candidate is not None:
            if not isinstance(candidate, Lane):
                raise ValueError('Invalid lane')
            candidates.append(candidate)
    selected = max(candidates, key=LANES.index)
    return Routing(selected, not risk_assessed)


def after_failure(lane: Lane, *, lane_passes: int, total_passes: int,
                  no_progress_passes: int, cause: str, has_hypothesis: bool,
                  policy: Mapping[str, Any]) -> tuple[str, Lane]:
    validate_policy(policy)
    for count in (lane_passes, total_passes, no_progress_passes):
        if type(count) is not int or count < 0:
            raise ValueError('Counters must be nonnegative integers')
    if total_passes < lane_passes or no_progress_passes > total_passes:
        raise ValueError('Inconsistent pass counters')
    if cause == 'environment':
        return 'WAIT_ENVIRONMENT', lane
    if cause == 'capability':
        return 'WAIT_CAPABILITY', lane
    if cause != 'code':
        raise ValueError('Unknown failure cause')
    if lane == Lane.PRO_WEB:
        return 'REOPEN_CASE', lane
    if total_passes >= policy['max_coding_passes']:
        return 'ESCALATE', Lane.PRO_WEB
    if (lane_passes >= policy['max_passes_per_lane'] or
            no_progress_passes >= policy['max_no_progress_passes'] or
            not has_hypothesis):
        return 'ESCALATE', LANES[LANES.index(lane) + 1]
    return 'RETRY', lane


def solution_digest(files: Mapping[str, bytes]) -> str:
    """Hash explicit relative paths and bytes; not a safe filesystem collector."""
    if not files:
        raise ValueError('An empty solution cannot be approved')
    records = []
    seen = set()
    for path, content in sorted(files.items()):
        if (not isinstance(path, str) or not path or path.startswith('/') or
                '\\' in path or ':' in path or any(ord(c) < 32 for c in path) or
                any(part in {'', '.', '..'} for part in path.split('/'))):
            raise ValueError('Unsafe or noncanonical relative path')
        if path.casefold() in seen:
            raise ValueError('Case-insensitive path collision')
        seen.add(path.casefold())
        if not isinstance(content, bytes):
            raise ValueError('File content must be bytes')
        records.append({'path': path, 'sha256': hashlib.sha256(content).hexdigest()})
    encoded = json.dumps({'schema_version': 1, 'files': records},
                         sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def validate_advice(data: Mapping[str, Any], *, request_id: str, state_digest: str,
                    ordered_options: Sequence[str]) -> str:
    """Validate AgenticArch normalized scores, not any upstream wire schema."""
    expected = tuple(ordered_options)
    if len(expected) < 2 or len(set(expected)) != len(expected):
        raise ValueError('Need distinct declared options')
    if not _digest(state_digest):
        raise ValueError('Invalid expected state digest')
    if (type(data.get('schema_version')) is not int or data['schema_version'] != 1 or
            data.get('request_id') != request_id or
            data.get('state_digest') != state_digest or
            tuple(data.get('ordered_options', ())) != expected):
        raise ValueError('Advice identity or options mismatch')
    scores = data.get('scores')
    if not isinstance(scores, dict) or set(scores) != set(expected):
        raise ValueError('Score option set mismatch')
    for value in scores.values():
        if (type(value) not in (float, int) or not math.isfinite(value) or
                not 0 <= value <= 1):
            raise ValueError('Invalid probability')
    if not math.isclose(sum(scores.values()), 1.0, abs_tol=1e-6):
        raise ValueError('Normalized probabilities must sum to one')
    provenance = data.get('provenance', {})
    if not isinstance(provenance, dict):
        raise ValueError('Invalid provenance object')
    for key in ('model_revision', 'tokenizer_revision', 'backend', 'prompt_version'):
        if not isinstance(provenance.get(key), str) or not provenance[key].strip():
            raise ValueError('Missing scoring provenance')
    if data.get('calibration') not in {'uncalibrated', 'workload_validated'}:
        raise ValueError('Unknown calibration status')
    best = max(scores.values())
    ties = [key for key in expected if abs(scores[key] - best) <= 1e-12]
    if set(expected) <= {lane.value for lane in LANES}:
        selected = max(ties, key=lambda key: LANES.index(Lane(key)))
    else:
        selected = ties[0]
    if data.get('selected') != selected:
        raise ValueError('Selected option violates argmax/tie policy')
    return selected


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    case_id: str
    role: str
    phase: str  # reviewer_challenge, pro_response, initial, or review
    sequence: int  # Assigned by the coordinator, never a model-supplied timestamp.
    identity_verified: bool
    durable_output_verified: bool
    participant_identity: str | None = None
    participant_binding_digest: str | None = None


@dataclass(frozen=True)
class Review:
    role: str
    verdict: str
    solution_digest: str
    requirements_digest: str
    bundle_digest: str
    receipt_id: str


@dataclass(frozen=True)
class CaseReview:
    case_id: str
    solution_digest: str
    requirements_digest: str
    bundle_digest: str
    reviews: Sequence[Review]
    receipts: Sequence[Receipt]
    unresolved_blockers: Sequence[str] = ()
    manifest_verified: bool = False
    evidence_references_verified: bool = False
    required_deliverables_present: bool = False
    reviewer_identity: str | None = None
    participant_binding_digest: str | None = None


def convergence_errors(case: CaseReview) -> list[str]:
    errors: list[str] = []
    if not case.case_id or not all(_digest(value) for value in (
        case.solution_digest, case.requirements_digest, case.bundle_digest
    )):
        errors.append('invalid_case_identity_or_digest')
    for flag in ('manifest_verified', 'evidence_references_verified', 'required_deliverables_present'):
        if getattr(case, flag) is not True:
            errors.append(flag)
    if case.unresolved_blockers:
        errors.append('unresolved_blockers')
    if (case.reviewer_identity not in {'claude-fable-5-1', 'claude-opus-5-5'} or
            not _digest(case.participant_binding_digest)):
        errors.append('invalid_participant_binding')
    receipts = {r.receipt_id: r for r in case.receipts}
    if len(receipts) != len(case.receipts):
        errors.append('duplicate_receipt')
    sequences = [r.sequence for r in case.receipts]
    if (len(set(sequences)) != len(sequences) or
            any(type(n) is not int or n < 1 for n in sequences)):
        errors.append('invalid_receipt_sequence')
    valid = [r for r in case.receipts if (
        r.receipt_id and r.case_id == case.case_id and r.role in {'pro', 'reviewer'} and
        r.identity_verified is True and r.durable_output_verified is True and
        r.participant_binding_digest == case.participant_binding_digest and
        r.participant_identity == ('gpt-6-pro-web' if r.role == 'pro' else case.reviewer_identity)
    )]
    challenges = [r.sequence for r in valid if r.role == 'reviewer' and r.phase == 'reviewer_challenge']
    responses = [r.sequence for r in valid if r.role == 'pro' and r.phase == 'pro_response']
    valid_responses = [b for b in responses if any(a < b for a in challenges)]
    if not valid_responses:
        errors.append('missing_real_challenge_then_response')
    latest: dict[str, tuple[int, Review]] = {}
    used_receipts: set[str] = set()
    for review in case.reviews:
        receipt = receipts.get(review.receipt_id)
        if (receipt is None or receipt not in valid or receipt.role != review.role or
                review.verdict not in {'APPROVE', 'REVISE', 'BLOCKED'}):
            errors.append('invalid_review_receipt_or_verdict')
            continue
        if review.receipt_id in used_receipts:
            errors.append('duplicate_review_receipt')
        used_receipts.add(review.receipt_id)
        if receipt.sequence > latest.get(review.role, (-1, review))[0]:
            latest[review.role] = (receipt.sequence, review)
    for role in ('pro', 'reviewer'):
        if role not in latest:
            errors.append(f'missing_{role}_review')
            continue
        sequence, review = latest[role]
        if review.verdict != 'APPROVE':
            errors.append(f'{role}_not_approved')
        if (review.solution_digest, review.requirements_digest, review.bundle_digest) != (
            case.solution_digest, case.requirements_digest, case.bundle_digest
        ):
            errors.append(f'{role}_stale_approval')
        if role == 'pro' and valid_responses and sequence < min(valid_responses):
            errors.append('pro_approval_precedes_response')
        if any(r.role == role and r.sequence > sequence for r in valid):
            errors.append(f'{role}_latest_turn_unreviewed')
    return sorted(set(errors))


def debate_action(*, converged: bool, rounds_this_run: int,
                  unresolved_nonprogress_rounds: int,
                  policy: Mapping[str, Any]) -> str:
    validate_policy(policy)
    if any(type(n) is not int or n < 0 for n in (rounds_this_run, unresolved_nonprogress_rounds)):
        raise ValueError('Invalid round counter')
    if converged:
        return 'LOCAL_RECONCILIATION'
    if (rounds_this_run >= policy['debate']['max_rounds_per_run'] or
            unresolved_nonprogress_rounds >= policy['debate']['max_nonprogress_rounds']):
        return 'PAUSED'
    return 'CONTINUE_DEBATE'


@dataclass(frozen=True)
class Check:
    check_id: str
    snapshot_digest: str
    plan_digest: str
    command_digest: str
    status: str
    exit_code: int | None


@dataclass(frozen=True)
class Completion:
    snapshot_digest: str
    plan_digest: str
    required_checks: Mapping[str, str]  # check ID -> locked command digest
    checks: Sequence[Check]
    required_requirements: Sequence[str]
    requirement_evidence: Mapping[str, str]  # requirement ID -> verified snapshot
    scope_ok: bool = False
    regression_coverage: bool = False
    behavior_reviewed: bool = False
    delivery_completed: bool = False
    unresolved_findings: Sequence[str] = ()
    pro_required: bool = False
    case: CaseReview | None = None
    local_reconciled: bool = False
    material_local_change: bool = False
    expected_case_id: str | None = None
    expected_solution_digest: str | None = None
    expected_requirements_digest: str | None = None
    expected_bundle_digest: str | None = None
    expected_participant_binding_digest: str | None = None


def completion_errors(state: Completion) -> list[str]:
    errors: list[str] = []
    if not _digest(state.snapshot_digest) or not _digest(state.plan_digest):
        errors.append('invalid_snapshot_or_plan')
    if not state.required_checks:
        errors.append('no_required_checks')
    by_id = {check.check_id: check for check in state.checks}
    if len(by_id) != len(state.checks):
        errors.append('duplicate_check_results')
    if any(check.status != 'PASS' or type(check.exit_code) is not int or check.exit_code != 0
           for check in state.checks):
        errors.append('observed_check_not_passed')
    for check_id, command_digest in state.required_checks.items():
        check = by_id.get(check_id)
        if not check_id or not _digest(command_digest):
            errors.append('invalid_check_definition')
        if check is None:
            errors.append(f'missing_check:{check_id}')
        elif (check.snapshot_digest, check.plan_digest, check.command_digest) != (
                state.snapshot_digest, state.plan_digest, command_digest):
            errors.append(f'stale_or_wrong_check:{check_id}')
    if not state.required_requirements:
        errors.append('no_acceptance_requirements')
    if (len(set(state.required_requirements)) != len(state.required_requirements) or
            any(not value for value in state.required_requirements)):
        errors.append('invalid_requirement_ids')
    for requirement in state.required_requirements:
        if state.requirement_evidence.get(requirement) != state.snapshot_digest:
            errors.append(f'uncovered_requirement:{requirement}')
    for flag in ('scope_ok', 'regression_coverage', 'behavior_reviewed', 'delivery_completed'):
        if getattr(state, flag) is not True:
            errors.append(flag)
    if state.unresolved_findings:
        errors.append('unresolved_findings')
    if state.pro_required:
        if state.case is None:
            errors.append('missing_pro_case')
        else:
            if convergence_errors(state.case):
                errors.append('case_not_converged')
            expected = (state.expected_case_id, state.expected_solution_digest,
                        state.expected_requirements_digest, state.expected_bundle_digest,
                        state.expected_participant_binding_digest)
            actual = (state.case.case_id, state.case.solution_digest,
                      state.case.requirements_digest, state.case.bundle_digest,
                      state.case.participant_binding_digest)
            if actual != expected:
                errors.append('case_not_bound_to_local_task')
        if state.local_reconciled is not True:
            errors.append('local_reconciliation_required')
        if state.material_local_change:
            errors.append('material_local_change_requires_review')
    return sorted(set(errors))


@dataclass(frozen=True)
class ProTransportCapability:
    """Trusted-adapter observations only; a model cannot certify these fields."""
    mode: str = 'manual'
    platform_permits_chatgpt_automation: bool = False
    permission_evidence_ref: str | None = None
    local_tool_verified: bool = False
    first_send_and_continuation_verified: bool = False
    export_authorized: bool = False
    unattended_required: bool = False


def pro_transport_action(cap: ProTransportCapability) -> str:
    """Fail-closed planning gate; it does not make an actual external request."""
    flags = (cap.platform_permits_chatgpt_automation, cap.local_tool_verified,
             cap.first_send_and_continuation_verified, cap.export_authorized,
             cap.unattended_required)
    if any(type(value) is not bool for value in flags):
        raise ValueError('Capability flags must be booleans')
    if cap.mode not in {'manual', 'supported_ui'}:
        raise ValueError('Unknown Pro web transport; no implicit substitute')
    if not cap.export_authorized:
        return 'WAIT_PERMISSION'
    if cap.mode == 'manual':
        return 'WAIT_CAPABILITY' if cap.unattended_required else 'WAIT_MANUAL_TRANSFER'
    if not (cap.platform_permits_chatgpt_automation and cap.local_tool_verified and
            cap.first_send_and_continuation_verified and
            isinstance(cap.permission_evidence_ref, str) and
            cap.permission_evidence_ref.strip()):
        return 'WAIT_CAPABILITY'
    return 'READY_FOR_PERMITTED_UI'

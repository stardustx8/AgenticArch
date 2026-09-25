"""CLM route compiler and deterministic subscription/effort guards.

All capability, task-risk and application receipts come from trusted adapters,
not from the model. This module performs no worker or account actions.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Callable, Mapping
from .clm import PreparedChoice, normalize_choice, prepare_choice, render_state
from .core import PRO_CATEGORIES

MENUS = {'luna': ('low', 'high'), 'astra': ('high',),
         'opus55': ('medium', 'high'), 'fable51': ('high',), 'pro': (None,),
         'fable55': ()}
BANDS = {'routine': 0, 'bounded': 1, 'medium_tough': 2, 'tough': 3}
REVIEWERS = {'fable51', 'opus55'}
TRANSPORTS = {'native_codex_subscription', 'native_claude_code_subscription',
              'qualified_pi_openai_subscription', 'chatgpt_web_subscription'}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def validate_catalog(catalog: Mapping[str, Any]) -> None:
    if catalog.get('schema_version') != 1 or set(catalog.get('models', {})) != set(MENUS):
        raise ValueError('Unknown catalog version or model set')
    for key, menu in MENUS.items():
        model = catalog['models'][key]
        if tuple(model.get('efforts', [])) != menu:
            raise ValueError('Effort menu changed without a policy revision')
        if key == 'fable55':
            if model.get('status') != 'pending' or model.get('provider_id') is not None:
                raise ValueError('Future model is not an active route')
        elif model.get('status') != 'candidate' or not model.get('identity'):
            raise ValueError('Model identity and candidate status required')
    if not catalog.get('routes'):
        raise ValueError('No routes')
    for key, route in catalog['routes'].items():
        family = route.get('model')
        if family not in MENUS or route.get('effort') not in MENUS[family]:
            raise ValueError('Invalid model/effort route')
        if route.get('slot') not in {'worker', 'reviewer', 'anchor'}:
            raise ValueError('Invalid route slot')
        if (type(route.get('tier')) is not int or route['tier'] not in range(4) or
                not route.get('description') or not route.get('evidence')):
            raise ValueError('Route needs tier, prose and evidence')
        if route['slot'] == 'anchor' and (family != 'pro' or route['tier'] != 3):
            raise ValueError('Only Pro is the deep anchor')
        if route['slot'] == 'reviewer' and (family not in REVIEWERS or route['effort'] != 'high'):
            raise ValueError('Invalid Claude participant')
        if route['slot'] == 'worker' and (family not in {'luna', 'astra', 'opus55'} or
                route['tier'] != (0 if family == 'luna' and route['effort'] == 'low' else
                                  1 if family == 'luna' else 2)):
            raise ValueError('Invalid worker family')


@dataclass(frozen=True)
class Capability:
    identity: str
    efforts: tuple[str | None, ...]
    transport: str
    observed_at: float
    permitted: bool = False
    subscribed: bool = False
    quota_available: bool = False
    qualified: bool = False


@dataclass(frozen=True)
class Task:
    complexity: str
    goal: str
    snapshot: str
    requirements: str
    categories: tuple[str, ...] = ()
    assessed: bool = False


def eligible(catalog: Mapping[str, Any], task: Task, capabilities: Mapping[str, Capability], *,
             profile: str, slot: str, now: float, max_age: float = 300) -> dict[str, dict]:
    validate_catalog(catalog)
    if task.complexity not in BANDS or set(task.categories) - PRO_CATEGORIES:
        raise ValueError('Unknown task classification')
    if profile not in {'codex', 'pi'} or slot not in {'worker', 'anchor', 'reviewer'}:
        raise ValueError('Unknown profile or slot')
    if not all(isinstance(v, str) and v.strip() for v in (task.goal, task.snapshot, task.requirements)):
        raise ValueError('Task evidence bindings required')
    if not math.isfinite(now) or not math.isfinite(max_age) or max_age <= 0:
        raise ValueError('Invalid freshness window')
    if task.assessed is not True:
        return {}  # Assessment is separate; uncertainty does not authorize edits.
    deep = bool(task.categories) or task.complexity == 'tough'
    if (slot == 'worker' and deep) or (slot != 'worker' and not deep):
        return {}
    out = {}
    for key, route in catalog['routes'].items():
        if route['slot'] != slot or (slot == 'worker' and route['tier'] < BANDS[task.complexity]):
            continue
        cap = capabilities.get(route['model'])
        model = catalog['models'][route['model']]
        if cap is None or any(getattr(cap, field) is not True for field in
                              ('permitted', 'subscribed', 'quota_available', 'qualified')):
            continue
        if (not math.isfinite(cap.observed_at) or not 0 <= now - cap.observed_at <= max_age or
                cap.identity != model['identity'] or route['effort'] not in cap.efforts):
            continue
        expected = ('chatgpt_web_subscription' if route['model'] == 'pro' else
                    'native_claude_code_subscription' if route['model'] in REVIEWERS else
                    'native_codex_subscription')
        allowed = {expected}
        if profile == 'pi' and expected == 'native_codex_subscription':
            allowed.add('qualified_pi_openai_subscription')
        if cap.transport not in allowed or cap.transport not in TRANSPORTS:
            continue
        out[key] = dict(route)
    return out


@dataclass(frozen=True)
class RoutePlan:
    request: PreparedChoice
    eligibility_digest: str
    route_ids: tuple[str, ...]
    baseline: str


def compile_route(catalog: Mapping[str, Any], task: Task, capabilities: Mapping[str, Capability], *,
                  profile: str, slot: str, now: float, baseline: str,
                  clm_model: str, provenance: Mapping[str, str],
                  token_counter: Callable[[str], int], max_tokens: int = 2048) -> RoutePlan:
    routes = eligible(catalog, task, capabilities, profile=profile, slot=slot, now=now)
    if not routes or baseline not in routes:
        raise ValueError('No qualified baseline; pause for capability/assessment')
    binding = digest({'catalog': catalog, 'task': task.__dict__, 'profile': profile,
                      'slot': slot, 'routes': routes,
                      'capabilities': {k: v.__dict__ for k, v in capabilities.items()}})
    state = render_state({'Task': task.goal, 'Complexity': task.complexity,
                          'Required role': slot, 'Harness': profile,
                          'Evidence binding': binding,
                          'Rule': 'Choose task fit only from the permitted candidates; insufficient is allowed.'})
    options = {key: route['description'] for key, route in routes.items()}
    options['insufficient'] = 'The supplied evidence does not justify choosing a different route; retain the verified baseline.'
    request = prepare_choice(state, 'Which permitted execution route best fits the work?', options,
                             model=clm_model, provenance=provenance,
                             token_counter=token_counter, max_tokens=max_tokens)
    return RoutePlan(request, binding, tuple(routes), baseline)


def resolve_route(plan: RoutePlan, response: Mapping[str, Any], *, refreshed: RoutePlan,
                  mode: str = 'shadow', qualified_policy_digest: str | None = None) -> str:
    """Recompile with fresh capability observations immediately before dispatch."""
    if mode not in {'shadow', 'advisory'} or plan.eligibility_digest != refreshed.eligibility_digest:
        raise ValueError('Invalid mode or stale route eligibility')
    if (plan.route_ids != refreshed.route_ids or plan.baseline != refreshed.baseline or
            plan.request.request_id != refreshed.request.request_id):
        raise ValueError('Decision plan changed')
    result = normalize_choice(plan.request, response)
    if mode == 'shadow' or result['status'] == 'ABSTAIN':
        return plan.baseline
    if qualified_policy_digest != plan.eligibility_digest:
        raise ValueError('Trusted workload qualification not bound to this policy and capability set')
    if result['selected'] not in refreshed.route_ids:
        raise ValueError('Unqualified route')
    return result['selected']


@dataclass(frozen=True)
class Boundary:
    session_id: str
    model: str
    generation: int
    revision: str  # changes on input/failure/model/manual override/compaction/policy/capability changes
    streaming: bool = False
    manual_override: bool = False


@dataclass(frozen=True)
class EffortLease:
    session_id: str
    model: str
    effort: str
    first_generation: int
    last_generation: int
    revision: str
    applied_receipt: str


def accept_effort(boundary: Boundary, *, effort: str, generations: int, minimum: str,
                  effective_model: str, effective_effort: str, effective_generation: int,
                  applied_receipt: str) -> EffortLease:
    menu = MENUS.get(boundary.model, ())
    if (boundary.streaming is not False or boundary.manual_override is not False or
            type(boundary.generation) is not int or boundary.generation < 1 or
            not boundary.session_id or not boundary.revision):
        raise ValueError('Not an authorized generation boundary')
    if (None in menu or effort not in menu or minimum not in menu or
            menu.index(effort) < menu.index(minimum) or
            type(generations) is not int or generations not in (1, 2, 5, 10)):
        raise ValueError('Invalid effort, floor or lease length')
    if (effective_model, effective_effort, effective_generation) != (boundary.model, effort, boundary.generation):
        raise ValueError('Requested setting was not applied exactly')
    if not isinstance(applied_receipt, str) or not applied_receipt.strip():
        raise ValueError('An actual adapter acknowledgement is required')
    return EffortLease(boundary.session_id, boundary.model, effort, boundary.generation,
                       boundary.generation + generations - 1, boundary.revision, applied_receipt)


def lease_valid(lease: EffortLease, boundary: Boundary) -> bool:
    return (boundary.streaming is False and boundary.manual_override is False and
            (lease.session_id, lease.model, lease.revision) ==
            (boundary.session_id, boundary.model, boundary.revision) and
            type(boundary.generation) is int and
            lease.first_generation <= boundary.generation <= lease.last_generation)


def quota_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> float | None:
    """Return comparable allowance depletion; unknown/reset/concurrent use is null."""
    keys = ('pool', 'window', 'reset_at', 'plan', 'measurement_protocol')
    if any(not before.get(k) or before.get(k) != after.get(k) for k in keys):
        return None
    if any(x.get('isolated') is not True for x in (before, after)):
        return None
    values = [x.get('used_fraction') for x in (before, after)]
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
        return None
    return values[1] - values[0] if values[1] >= values[0] else None


def compile_effort(catalog: Mapping[str, Any], boundary: Boundary, *, minimum: str,
                   evidence: str, clm_model: str, provenance: Mapping[str, str],
                   token_counter: Callable[[str], int], max_tokens: int = 2048) -> PreparedChoice | None:
    """Return no request for a fixed menu; one setting needs no semantic call."""
    validate_catalog(catalog)
    if boundary.streaming or boundary.manual_override or not boundary.revision:
        raise ValueError('No dynamic change at this boundary')
    menu = MENUS.get(boundary.model, ())
    if None in menu or minimum not in menu or not evidence.strip():
        raise ValueError('Invalid model, step floor or evidence')
    choices = menu[menu.index(minimum):]
    if len(choices) == 1:
        return None
    descriptions = catalog['effort_question']['descriptions']
    criteria = {key: descriptions[key] for key in choices}
    criteria['insufficient'] = descriptions['insufficient']
    state = render_state({'Current model': boundary.model, 'Next-step evidence': evidence,
                          'Boundary binding': digest(boundary.__dict__), 'Minimum effort': minimum})
    return prepare_choice(state, catalog['effort_question']['instructions'], criteria,
                          model=clm_model, provenance=provenance, token_counter=token_counter,
                          max_tokens=max_tokens, question_id='effort')

"""Deterministic route eligibility and compact CLM candidate rendering.

Catalog facts are curated evidence, never permission. Runtime bindings are trusted
local observations with an expiry, not fields a model is allowed to attest itself.
"""
from __future__ import annotations
from typing import Mapping
import math
from .core import PRO_CATEGORIES
from .clm import Choice

ROLES = {'implementation', 'deep_anchor', 'deep_partner'}
METHODS = {'codex_subscription', 'claude_code_subscription', 'chatgpt_web_subscription',
           'pi_openai_subscription'}


def validate_catalog(catalog: dict) -> None:
    if catalog.get('schema_version') != 2 or catalog.get('mode') not in {'shadow', 'advisory'}:
        raise ValueError('Invalid routing catalog version/mode')
    models, routes = catalog.get('models'), catalog.get('routes')
    if not isinstance(models, dict) or not isinstance(routes, dict) or not routes:
        raise ValueError('Model and route dictionaries are required')
    for name, model in models.items():
        if model.get('status') not in {'released', 'pending'} or not isinstance(model.get('allowed_efforts'), list):
            raise ValueError('Invalid model declaration')
        if model['status'] == 'pending' and model['allowed_efforts']:
            raise ValueError('Pending models cannot be assigned active efforts')
        if not model.get('evidence_ids'):
            raise ValueError('Model decisions need evidence or explicit owner provenance')
    for key, route in routes.items():
        model = models.get(route.get('model'))
        if (not model or model['status'] != 'released' or
                route.get('effort') not in model['allowed_efforts'] or
                route.get('role') not in ROLES or type(route.get('tier')) is not int or
                route['tier'] not in range(4) or not route.get('description')):
            raise ValueError('Invalid route/model/effort')
        if not route.get('methods') or set(route['methods']) - METHODS:
            raise ValueError('Route includes an unapproved billing transport')
    required = {'luna_low', 'luna_high', 'astra_high', 'opus_medium', 'opus_high',
                'pro_web', 'fable_review', 'opus_review'}
    if set(routes) != required:
        raise ValueError('Unexpected route set; change policy explicitly')
    bounds = {
        'luna_low': ('luna', 'low', 0, 'implementation'),
        'luna_high': ('luna', 'high', 1, 'implementation'),
        'astra_high': ('astra', 'high', 2, 'implementation'),
        'opus_medium': ('opus', 'medium', 2, 'implementation'),
        'opus_high': ('opus', 'high', 2, 'implementation'),
        'pro_web': ('pro', None, 3, 'deep_anchor'),
        'fable_review': ('fable', 'high', 3, 'deep_partner'),
        'opus_review': ('opus', 'high', 3, 'deep_partner'),
    }
    for key, expected in bounds.items():
        if tuple(routes[key].get(f) for f in ('model', 'effort', 'tier', 'role')) != expected:
            raise ValueError('Route semantics do not match owner policy')
    identities = {
        'luna': ('gpt-6-luna', ['low', 'high'], 'high'),
        'astra': ('gpt-6-astra', ['high'], 'high'),
        'opus': ('claude-opus-5-5', ['medium', 'high'], 'medium'),
        'fable': ('claude-fable-5-1', ['high'], 'high'),
        'pro': ('gpt-6-pro-web', [None], None),
    }
    if set(models) != set(identities) | {'fable_next'}:
        raise ValueError('Unexpected model set; change the policy explicitly')
    for key, (identity, efforts, default) in identities.items():
        m = models[key]
        if (m.get('identity') != identity or m.get('status') != 'released' or
                m.get('allowed_efforts') != efforts or m.get('default_effort') != default):
            raise ValueError('Model identity/default/effort menu does not match policy')
    pending = models['fable_next']
    if (pending.get('status') != 'pending' or pending.get('identity') is not None or
            pending.get('automatic_activation') is not False):
        raise ValueError('Future Fable must remain inactive until explicit qualification')
    for key, r in routes.items():
        expected_methods = ({'codex_subscription', 'pi_openai_subscription'}
            if r['model'] in {'luna', 'astra'} else
            {'chatgpt_web_subscription'} if r['model'] == 'pro' else
            {'claude_code_subscription'})
        if set(r['methods']) != expected_methods:
            raise ValueError('Provider transport does not match the subscription contract')


def eligible_routes(catalog: dict, bindings: Mapping[str, dict], *, role: str,
                    tier: int, harness: str, now: float, categories: tuple[str, ...] = ()) -> dict:
    validate_catalog(catalog)
    if role not in ROLES or harness not in {'codex', 'pi'} or type(tier) is not int or tier not in range(4):
        raise ValueError('Invalid routing scope')
    if type(now) not in (float, int) or not math.isfinite(now):
        raise ValueError('Invalid observation clock')
    if set(categories) - PRO_CATEGORIES:
        raise ValueError('Unknown risk category requires assessment')
    if role == 'implementation' and (categories or tier == 3):
        role = 'deep_anchor'
    out = {}
    for name, route in catalog['routes'].items():
        if route['role'] != role or (role == 'implementation' and route['tier'] < tier):
            continue
        b = bindings.get(name, {})
        model = catalog['models'][route['model']]
        expiry = b.get('expires_at')
        if (type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= now or
                b.get('harness') != harness or b.get('model_id') != model['identity'] or
                b.get('effort') != route['effort'] or b.get('method') not in route['methods'] or
                b.get('billing_mode') != 'subscription' or
                any(b.get(flag) is not True for flag in ('available', 'permission_verified',
                    'identity_verified', 'integration_tested', 'extra_usage_disabled')) or
                b.get('quota_exhausted') is not False or b.get('fallback_detected') is not False):
            continue
        if b['method'] == 'pi_openai_subscription' and (harness != 'pi' or
                b.get('native_subscription_permission_verified') is not True):
            continue
        # Never put Claude subscription tokens into Pi's provider layer.
        if route['model'] in {'opus', 'fable'} and b['method'] != 'claude_code_subscription':
            continue
        out[name] = route
    return out


def request_parts(task: Mapping[str, object], candidates: Mapping[str, dict]) -> tuple[str, str, dict]:
    if not candidates:
        raise ValueError('WAIT_CAPABILITY: no qualified subscription route')
    required = ('goal', 'next_step', 'constraints', 'evidence_summary')
    if any(not isinstance(task.get(k), str) or not task[k].strip() for k in required):
        raise ValueError('Missing task facts; do not fabricate a state')
    fields = required + ('domain', 'language', 'failure_summary', 'quota_observation')
    state = '\n\n'.join(f'{key}: {task[key]}' for key in fields if task.get(key))
    descriptions = {name: spec['description'] for name, spec in candidates.items()}
    descriptions['ABSTAIN'] = 'The available evidence does not distinguish these routes safely. Ask the coordinator for more evidence.'
    question = 'Which permitted route best fits the NEXT step under these constraints? Candidate capabilities are provisional. Abstain when uncertain.'
    return state, question, descriptions


def resolve_advice(choice: Choice, candidates: Mapping[str, dict], *, mode: str,
                   qualified_workload: bool, expected_request_digest: str,
                   expected_deployment_digest: str) -> str | None:
    if mode not in {'shadow', 'advisory'} or choice.request_digest != expected_request_digest:
        raise ValueError('Wrong decision mode or stale request')
    if choice.deployment_digest != expected_deployment_digest:
        raise ValueError('Stale CLM deployment')
    values = choice.probabilities.values()
    if any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in values) or not math.isclose(sum(values), 1.0, abs_tol=1e-6):
        raise ValueError('Invalid scores')
    if set(choice.probabilities) != set(candidates) | {'ABSTAIN'}:
        raise ValueError('Stale or unfiltered candidate set')
    if mode == 'shadow' or qualified_workload is not True or choice.selected == 'ABSTAIN':
        return None
    best = max(choice.probabilities.values())
    if sum(abs(v - best) <= 1e-12 for v in choice.probabilities.values()) != 1:
        return None
    if choice.selected not in candidates or choice.probabilities[choice.selected] != best:
        raise ValueError('Invalid route choice')
    return choice.selected  # Suggestion only. Recheck binding immediately before dispatch.


def effort_options(catalog: dict, model_key: str, *, minimum: str,
                   role: str = 'implementation', max_generations: int = 10) -> dict[str, dict]:
    """Finite joint effort/lease actions; IDs map to local parameters, never commands."""
    validate_catalog(catalog)
    model = catalog['models'].get(model_key)
    if (not model or model['status'] != 'released' or model_key == 'pro' or
            role not in {'implementation', 'deep_partner'} or
            type(max_generations) is not int or max_generations not in {1, 2, 5, 10}):
        raise ValueError('No qualified effort menu for this model/scope')
    allowed = model['allowed_efforts']
    if minimum not in allowed or (role == 'deep_partner' and
            (model_key not in {'opus', 'fable'} or minimum != 'high')):
        raise ValueError('Invalid next-step minimum or deep-review effort')
    meanings = {
        'low': 'Perform a narrow mechanical step with little deliberation and a known contract.',
        'medium': 'Perform ordinary medium-tough implementation with bounded reasoning.',
        'high': 'Reason carefully about substantive logic, interactions or difficult evidence.',
    }
    options = {}
    for effort in allowed[allowed.index(minimum):]:
        for n in (1, 2, 5, 10):
            if n <= max_generations:
                options[f'{effort}_for_{n}'] = {
                    'effort': effort, 'generations': n,
                    'description': meanings[effort] + f' Retain this setting for {n} generation(s) unless an invalidating event occurs.',
                }
    return options

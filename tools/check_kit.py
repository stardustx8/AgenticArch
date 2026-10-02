#!/usr/bin/env python3
"""Dependency-free repository consistency checks; no model or network calls."""
from pathlib import Path
import json
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.core import validate_advice, validate_policy
from reference.decision_plane import stages
from reference.routing import validate_catalog


def main() -> int:
    errors = []
    for path in ROOT.rglob('*.json'):
        if '.git' in path.parts:
            continue
        try:
            json.loads(path.read_text())
        except (ValueError, OSError) as exc:
            errors.append(f'{path.relative_to(ROOT)}: {exc}')
    try:
        policy = json.loads((ROOT / 'config/policy.json').read_text())
        validate_policy(policy)
        catalog = json.loads((ROOT / 'config/model-routing.json').read_text())
        validate_catalog(catalog)
        if catalog['mode'] != policy['clm']['mode']:
            raise ValueError('Catalog and policy disagree about CLM mode')
        sources = json.loads((ROOT / 'config/research-evidence.json').read_text())['sources']
        for model in catalog['models'].values():
            if set(model['evidence_ids']) - set(sources):
                raise ValueError('Unknown model evidence reference')
        for prior in catalog['priors']:
            if set(prior['basis']) - set(sources):
                raise ValueError('Unknown prior evidence reference')
        operators = json.loads((ROOT / 'config/decision-operators.json').read_text())
        if operators.get('schema_version') != 1 or not operators.get('operators'):
            raise ValueError('Invalid decision operator catalog')
        stages(operators['operators'])
        fixture = json.loads((ROOT / 'examples/clm-advice.json').read_text())
        validate_advice(fixture, request_id=fixture['request_id'],
                       state_digest=fixture['state_digest'],
                       ordered_options=fixture['ordered_options'])
        case_states = json.loads((ROOT / 'schemas/case.schema.json').read_text())['properties']['status']['enum']
        if not {'WAIT_PERMISSION', 'WAIT_MANUAL_TRANSFER', 'WAIT_CAPABILITY'} <= set(case_states):
            raise ValueError('Case schema omits a required transport wait state')
        profile = json.loads((ROOT / 'harnesses/codex/profile.json').read_text())
        if profile['billing'] != 'subscription_only' or profile['api_fallback'] is not False:
            raise ValueError('Invalid Codex harness billing profile')
        for name in ('prepare-sol-pro-architecture-review', 'fable-adversarial-review'):
            base = ROOT / 'skills' / name
            if (base / 'references/protocol.md').read_bytes() != (
                    ROOT / 'skills/prepare-sol-pro-architecture-review/references/protocol.md').read_bytes():
                raise ValueError('Portable skill protocol drift')
        from aa.workers import LANES
        from aa.tasks import TIERS
        from aa.decisions import CHOSEN, PEER_LANES, peer_question, tier_question
        if (any(set(tier_question(b)[1]) != set(TIERS) for b in CHOSEN) or
                not set(PEER_LANES.values()) <= set(LANES) or
                any(set(peer_question(b)[1]) != set(PEER_LANES) for b in CHOSEN)):
            raise ValueError('Runtime tiers/lanes inconsistent')
    except (ValueError, KeyError, OSError) as exc:
        errors.append(f'Policy/catalog/fixture: {exc}')
    for path in ROOT.rglob('*.md'):
        if '.git' in path.parts or 'archive' in path.parts or 'parked' in path.parts:
            continue
        for target in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', path.read_text()):
            if target.startswith(('#', 'https://', 'http://', 'mailto:')):
                continue
            target = unquote(target.split('#', 1)[0])
            if not (path.parent / target).exists():
                errors.append(f'{path.relative_to(ROOT)}: missing link {target}')
    required = (
        'README.md', 'START-HERE.md', 'AGENTS.md', 'IMPLEMENTATION-STATUS.md',
        'docs/RUNTIME.md', 'docs/ARCHITECTURE.md', 'docs/SESSION-HANDOFF.md', 'docs/DECISIONS.md',
        'docs/OWNER-REQUIREMENTS.md', 'eval/RESULTS.md', 'aa/daemon.py', 'aa/cases.py',
        'aa/tasks.py', 'aa/workers.py', 'aa/clm.py', 'bin/aa', 'deploy/systemd/aa-daemon.service',
        'deploy/systemd/aa-semif.service', 'deploy/semif/semif_server.py', 'aa/semif.py', 'aa/rules.py',
        'reference/core.py', 'reference/clm.py', 'reference/effort.py', 'tests/test_aa_runtime.py',
        'skills/agenticarch/SKILL.md', 'skills/prepare-sol-pro-architecture-review/SKILL.md',
        'skills/fable-adversarial-review/SKILL.md')
    for name in required:
        if not (ROOT / name).is_file():
            errors.append(f'Missing {name}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('PASS: policy/catalog JSON, operators, CLM fixture, Codex profile, runtime lanes/tiers, skills and local links')
    print('NOT CHECKED: live integrations, accuracy, quota savings, Git publication or full JSON Schema semantics')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

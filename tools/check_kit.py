#!/usr/bin/env python3
"""Dependency-free kit consistency checks; no network or model invocation."""
from pathlib import Path
import json
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.core import validate_advice, validate_policy
from reference.decision_plane import stages


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
        validate_policy(json.loads((ROOT / 'config/policy.json').read_text()))
        catalog = json.loads((ROOT / 'config/decision-operators.json').read_text())
        if catalog.get('schema_version') != 1 or not catalog.get('operators'):
            raise ValueError('Invalid decision operator catalog')
        stages(catalog['operators'])
        fixture = json.loads((ROOT / 'examples/semif-advice.json').read_text())
        validate_advice(fixture, request_id=fixture['request_id'],
                       state_digest=fixture['state_digest'],
                       ordered_options=fixture['ordered_options'])
    except (ValueError, KeyError) as exc:
        errors.append(f'Policy/operator catalog/fixture: {exc}')
    for path in ROOT.rglob('*.md'):
        if '.git' in path.parts:
            continue
        text = path.read_text()
        # Check local Markdown links, not unrendered command/code paths or URL anchors.
        for target in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', text):
            if target.startswith(('#', 'https://', 'http://', 'mailto:')):
                continue
            target = unquote(target.split('#', 1)[0])
            if not (path.parent / target).exists():
                errors.append(f'{path.relative_to(ROOT)}: missing link {target}')
    for required in ('README.md', 'START-HERE.md', 'AGENTS.md', 'IMPLEMENTATION-STATUS.md',
                     'docs/SESSION-HANDOFF.md', 'docs/DECISIONS.md',
                     'docs/STATE-MACHINE.md', 'prompts/IMPLEMENT-AGENTICARCH.md',
                     'reference/core.py', 'tests/test_core.py',
                     'reference/decision_plane.py', 'tests/test_decision_plane.py',
                     'docs/OWNER-REQUIREMENTS.md', 'docs/RESEARCH-SOURCES.md',
                     'docs/DECISION-PLANE.md', 'docs/DECISION-EVALUATION.md',
                     'docs/SEMANTIC-DECISION-OPPORTUNITIES.md',
                     'skills/prepare-sol-pro-architecture-review/SKILL.md',
                     'skills/fable-adversarial-review/SKILL.md'):
        if not (ROOT / required).is_file(): errors.append(f'Missing {required}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('PASS: JSON syntax, four-lane policy, operator catalog/dependencies, SemIf fixture, local links and required files')
    print('NOT CHECKED: live adapters, real skill migration, Git publication and full JSON Schema semantics')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

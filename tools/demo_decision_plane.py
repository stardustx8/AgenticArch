#!/usr/bin/env python3
"""Synthetic offline illustration: no model, tool execution or inferred success."""
from pathlib import Path
from dataclasses import asdict
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.decision_plane import digest, interpret, make_request


def main() -> int:
    operators = {op['id']: op for op in json.loads(
        (ROOT / 'config/decision-operators.json').read_text())['operators']}
    context = {
        'project_id': 'synthetic-job-service',
        'task_id': 'synthetic-disconnect-recovery',
        'snapshot_digest': digest({'synthetic_snapshot': 1}),
        'requirements_digest': digest({'durability': 'accepted jobs survive restarts'}),
        'policy_digest': digest({'synthetic_policy': 1}),
        'authorization_scope_digest': digest({'scope': 'synthetic-read-only'}),
        'model_revision': 'NOT_RUN:synthetic-fixture',
        'tokenizer_revision': 'NOT_RUN',
        'backend': 'synthetic',
        'quantization': 'not-applicable',
        'prompt_template_digest': digest({'fixture_template': 1}),
        'runtime_revision': 'offline-reference',
        'scoring_mode': 'synthetic',
        'calibration_id': 'UNQUALIFIED',
        'max_options': 16,
    }
    examples = [
        ('requirement_evidence', 'implementation_pass', {
            'requirement': 'An accepted job must survive a backend restart.',
            'evidence': 'Synthetic fixture: TCP reconnect test passes; no restart test exists.',
        }, 'insufficient'),
        ('next_diagnostic', 'verification_failed', {
            'goal': 'Find why a job cannot be retrieved after a backend restart.',
            'failure': 'Synthetic fixture: job retrieval after restart returns not found.',
            'diagnostic_menu': ['inspect_contract', 'reproduce_failure', 'inspect_recent_change'],
        }, 'inspect_contract'),
    ]
    result = {'warning': 'SYNTHETIC scores only. No CLM inference or project test was run.',
              'records': []}
    for operator_id, event, state, selected in examples:
        request = make_request(operators[operator_id], state, context, event=event)
        option_ids = [option['id'] for option in operators[operator_id]['options']]
        # Fixture values exercise the contract; they are not measured confidence.
        scores = {key: 0.8 if key == selected else 0.2 / (len(option_ids) - 1)
                  for key in option_ids}
        response = {'request_id': request['request_id'], 'selected': selected, 'scores': scores}
        advice = interpret(request, response, qualified=False)
        assert advice.status in {'SHADOW', 'ABSTAIN'} and advice.influence is None
        result['records'].append({'operator': operator_id, 'request_id': request['request_id'],
                                  'advice': asdict(advice), 'executed_action': None})
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

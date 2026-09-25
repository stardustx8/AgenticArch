#!/usr/bin/env python3
"""Print synthetic CLM route/effort templates; never call a model or execute a job."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.routing import eligible_routes, request_parts, effort_options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--harness', choices=['codex', 'pi'], default='codex')
    args = parser.parse_args()
    catalog = json.loads((ROOT / 'config/model-routing.json').read_text())
    # Deliberately transient fixtures, not installed capability or billing evidence.
    bindings = {}
    for name, route in catalog['routes'].items():
        bindings[name] = dict(harness=args.harness, model_id=catalog['models'][route['model']]['identity'],
            effort=route['effort'], method=route['methods'][0], billing_mode='subscription', expires_at=1,
            available=True, permission_verified=True, identity_verified=True,
            integration_tested=True, extra_usage_disabled=True, quota_exhausted=False, fallback_detected=False)
    eligible = eligible_routes(catalog, bindings, role='implementation', tier=2, harness=args.harness, now=0)
    state, question, choices = request_parts(dict(goal='Implement an approved dashboard form',
        next_step='Connect validation and error handling to existing APIs',
        constraints='Preserve API contracts and existing accessibility checks',
        evidence_summary='The approved specification and component tests are available', domain='frontend'), eligible)
    print(json.dumps(dict(synthetic=True, executed=False, tokenizer_validation='NOT_RUN',
        harness=args.harness, route=dict(state=state, questions={'route':dict(type='choice', instructions=question, criteria=choices)}),
        effort_lease_options=effort_options(catalog,'opus',minimum='medium',max_generations=2)), indent=2))


if __name__ == '__main__':
    main()

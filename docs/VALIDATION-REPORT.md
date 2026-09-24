# Offline validation report

Date: 2026-09-24. Preparation environment: Linux, Python 3.13.5.

## Executed

| Check | Result | Scope |
| --- | --- | --- |
| `python3 -m unittest discover -s tests -v` | 93 tests passed | Policy floors, model/effort validation, evidence and exact-version convergence, transport qualification, installer safety, decision request identity, dependency stages, malformed/stale responses and abstention |
| `python3 tools/check_kit.py` | Passed | JSON syntax, strict policy validation, nine operator contracts and dependency graph, SemIf fixture, local Markdown links and required artifacts |
| `python3 tools/demo_decision_plane.py` | Passed | Synthetic, unqualified decision responses produce abstention/shadow records and no action |

The test count is not an accuracy measurement, security certification or proof of end-to-end operation. The tests are written and run during kit preparation; no independent Pro/Fable review was performed here.

## Not executed

Actual SemIf scoring and calibration, custom Codex model dispatch, user-machine skill installation, browser automation, real Pro/Fable conversations, repository collaboration, production persistence/recovery and target-project acceptance tests remain **NOT_RUN**. Full JSON Schema semantic validation is not included in the dependency-free consistency command. Python 3.11 is the intended minimum; this preparation run tested 3.13.5, not a multi-version matrix.

All nine new semantic operators are configured in **shadow** mode. Their synthetic tests do not qualify them for live decision influence. Use the family-specific evaluation plan before enabling advisory behavior.

A source archive or initialized local Git repository is not proof of remote publication. Check the actual remote branch and commit as described in [publication guidance](PUBLISHING.md).

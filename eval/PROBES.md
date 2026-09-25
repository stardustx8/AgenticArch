# Where else a local decider helps (2026-09-25)

Research (SemIf's own benchmarks, web evidence on small classifiers in agent harnesses)
plus four probes on this harness's real decision points. Blind data from separate Opus
runs (secret_leak is author-written and generated locally, gitignored). Full table:
`20260925-1822-probes.md` in results/. All numbers on the test split (n = 40-45 per probe).

| Decision point | SemIf | Regex rules | Extra Codex Luna low call | Verdict |
| --- | --- | --- | --- | --- |
| Outbound secret gate (candidate from regex: real secret?) | 100% secret recall, 9/22 false alarms | 73% recall | 100% (but sends the secret to a remote model) | **Use SemIf** — must stay local |
| Check failure: environment vs code | env recall 100%, precision 83% at conf>=0.5 | 60% overall | 87% overall, 4.5 s + quota per failure | **Use SemIf** + deterministic rerun (flaky) and base-commit run (pre-existing) |
| Worker outcome done/partial/blocked | 93% | 51% | 98% | Prefer structured status from the worker itself (schema field, no extra call) |
| Test tampering (checks passed dishonestly) | 78%, tampered recall 55% | 60% | 100% | **Use Codex review**, SemIf too weak (small judges near chance, CodeJudgeBench) |
| Command risk guard | — | — | — | Use Claude Code's native sandbox + auto mode (needs socat) |
| Task tier / peer routing | 82% (holdout) | 57% | Codex triage 90% (already runs) | Codex alone (RESULTS.md) |

SemIf is worth keeping where a decision must stay on the machine or runs on every
event without a remote model in the loop, and only to flag/escalate — never to approve.

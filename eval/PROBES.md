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
| Spec conformance after each run (owner idea; blind, n=40) | whole spec 65% (catches 30%); per criterion 80% (catches 70%, 10% false send-backs) | always "matches" 50% | **90%, catches 100%, 20% false send-backs** | Opus 5.5 medium/high: **100%, 0 false send-backs** → **built with Opus medium (D017)**; SemIf pre-screen saves only 2/40 calls |
| Command risk guard | — | — | — | Use Claude Code's native sandbox + auto mode (needs socat) |
| Task tier / peer routing | 82% (holdout) | 57% | Codex triage 90% (already runs) | Codex alone (RESULTS.md) |

SemIf is worth keeping where a decision must stay on the machine or runs on every
event without a remote model in the loop, and only to flag/escalate — never to approve.

Spec-check loop design implied by the data: after checks pass, one Codex Luna low call
judges each acceptance criterion against the diff; unmet criteria go back to the same
worker lane with the judge's reason; the worker may rebut; at most 2 spec loops, then
the owner decides. A tuned-on-test SemIf gate looked like it saved 43% of judge calls;
re-tuned on dev only it saves 5% — a reminder why wording/thresholds are chosen on dev.

## Threshold calibration: environment vs code (2026-09-26)

Saved SemIf probabilities (`20260925-1822-probes.json`, question "cause"), environment =
top answer with confidence >= threshold. Chosen on dev (n=45, 15 env), reported on test (n=45, 15 env):

| threshold | dev F1 / false alarms / misses | test F1 / false alarms / misses |
| --- | --- | --- |
| 0.5 (old) | 0.87 / 2 / 2 | 0.91 / 3 / 0 |
| **0.7 (dev best, adopted)** | 0.90 / 1 / 2 | 0.91 / 3 / 0 |
| 0.95 | 0.85 / 0 / 4 | 0.90 / 1 / 2 |

The remaining false alarms are not borderline: missing in-repo modules / undefined symbols
("No module named 'shop.billing.tax_utils'", linker errors) get 0.96 "environment". No threshold
fixes these; context does (e.g. the files the worker changed: a missing module inside the repo is
code). Labels were re-read; no labelling errors found. Most "flaky" rows are caught live by the
deterministic rerun before SemIf is asked.

Follow-up, same day: repo context for the decider (Jev article idea "give it the source to
check against"). Opus wrote, blind to the labels, each row's top-level repo entries and the
files the change touched; SemIf saw them before the output. At 0.7 — plain: dev 1 false alarm /
2 misses, test 3 / 0; with context: dev 0 / 2, test 2 / 1 (an explicit "missing in-repo module
points to the code" hint: identical). No gain within noise (15 environment rows per split) ->
not built.

Follow-up (loop/jev article rules "give every choice an exit" and "calibration"): adding an
`other` option to the failure-cause question changed nothing useful (never picked; test: one
more missed environment failure) -> not adopted. Calibration of the current wording over all
90 rows: confidence 0.9+ n=69 accuracy 0.83; 0.6-0.9 n=9 0.67; 0.3-0.6 n=6 0.50; <0.3 n=6 0.00.
Confidence ranks correctly but SemIf is overconfident at the top, which supports using it
only to flag (never to decide alone).

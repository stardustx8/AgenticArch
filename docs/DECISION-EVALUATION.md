# Decision-plane evaluation and adoption gates

No accuracy, speedup or cost reduction for this workstation is claimed yet. The public examples test contracts with synthetic scores; they are not a semantic benchmark.

## Baselines

Compare the same scoped tasks under: (A) deterministic policy plus existing Codex/search; (B) SemIf routing advice alone; (C) one new decision family at a time; and (D) the useful combination. For retrieval, include the existing lexical/embedding/reranker route. For test selection, compare simple failure-location prioritization. For specialist training, compare the unchanged general SemIf backend. Include all failed and paused tasks.

Record accepted behavior, regressions, rework, mandatory-check coverage, time-to-first-reproducible-failure, human intervention, remote usage and local compute. Separately measure cold/warm scoring, prefill length, p50/p95 latency, batch size, peak GPU/system memory and interference with interactive coding. Do not optimize decision latency while making end-to-end tasks slower.

## Family-specific gates

| Family | Offline target | End-to-end target | Non-negotiable guard |
| --- | --- | --- | --- |
| Context | Relevant evidence recall at a fixed token budget; stale/irrelevant rejection | Accepted tasks with fewer missing-context repairs | Pinned evidence survives; scope isolation |
| Requirement gaps | Missed-gap and false-alert rates on seeded omissions | Real omitted behavior caught before completion | Predicate is never a test PASS |
| Diagnostic choice | Fraction yielding a useful discriminating observation | Fewer blind repair passes and faster reproduction | Mandatory checks never removed |
| Memory | Retrieval quality and stale-fact rejection | Useful prior discoveries reused correctly | Raw observations retained; no auto-promotion to owner authority |
| Debate triage | Duplicate-link precision; material-objection recall | Fewer redundant turns without lost dissent | Both participants still approve exact current digests |
| Drift | Sensitivity to small behavior changes; false-positive rate | Faithful local adaptation without unnecessary Pro loops | Material semantic changes reopen review |
| Playbooks | Known branch coverage; unexpected-state abstention | Lower overhead on repeated diagnostic patterns | Only vetted capabilities, bounded exits |
| Counterexamples | Independently valid reproductions per compute budget | Confirmed defects discovered before release | Trusted oracle separate from generated input |
| Event filtering | Blocker recall, notification count | Less noise with prompt blocker visibility | Required failures never hidden |
| Specialists | Held-out selective risk and latency vs SemIf | Actual resource benefit without quality loss | No automatic training/policy promotion |

## Data and labels

Use authorized project data only. Split by project/task root and time, not by randomly separating near-duplicate chunks or paraphrases. Lock a held-out final set before tuning. Capture the exact model/tokenizer/quantization/prompt/option order/serving configuration. Keep raw model scores, model-proposed labels, independent labels and post-deployment outcomes separate.

Log labels for uncertain cases **and a random sample of confident cases**; otherwise confident mistakes become invisible. Models agreeing is a weak label, not ground truth. Use actual test outcomes only for propositions those tests check; test success is not a universal product-quality label. Do not upload private training data just because a review repository is private.

Report denominators, confusion matrices, confidence intervals and uncertainty. Calibration metrics such as Brier score or NLL and reliability plots are separate from classification accuracy. A raw score threshold shared across all operators is unacceptable. Calibrate per family with a documented artifact and validate after distribution/backend changes. The word “calibrated” alone is not a promotion gate. [S03, S11 in RESEARCH-SOURCES.md]

## Required adversarial fixtures

Include missing relevant context, all options poor, ambiguous observations, paraphrased requirements, reversed option ordering, distractor evidence, injected instructions in logs, cross-project cache collisions, stale revisions, changed permissions, dependent questions submitted together, unsupported model/backends and memory pressure. Seed “passing” checks that test the wrong behavior, duplicate-looking objections that differ in a material detail, and confident but incorrect teacher labels.

Batch/shared-state modes must be compared against direct scoring. Any discrepancy is reported; equal aggregate accuracy is not bitwise equivalence. Small score differences near a boundary should abstain rather than trigger uncontrolled action. Use explicit tie behavior and an insufficient-evidence option.

## Promotion and rollback

Define acceptable errors, cost/time budgets and required sample sizes before examining the held-out result. Values are owner-approved deployment decisions, not invented universal constants. Start with low-consequence ranking assistance. Failed or inconclusive evidence leaves the family in shadow/off mode. An optional feature must not block independent core implementation.

Promotion records include operator/version, scope, data split, results, calibration identity, allowed influence, owner decision and rollback. Keep the previous version installed for a canary; regressions or unexpected distribution shift disable the affected family. Do not self-modify production policy or train weights inside the main coding loop.

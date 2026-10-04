# Decision benchmark results (2026-09-25)

Question: which local decider should vote on the task tier and the medium-tough model,
next to the Codex triage that already runs for every task — CLM, SemIf, or plain keyword
rules? Raw outputs: `results/20260925-1722` (CLM, SemIf, Codex on test),
`results/20260925-1725` (+ rules), `results/20260925-1730` (blind holdout).

## Data

- `decisions/tier.jsonl`: 120 tier + 40 peer rows written by Claude from the labelling
  guide (README). Wording chosen on `dev`, reported on `test` (60 rows).
- `decisions/holdout_opus.jsonl`: 80 **blind** rows written and labelled by a separate
  Opus 5.5 run that saw only the labelling guide (not the rules or the other rows);
  20 per tier, 20 deliberately misleading (`tricky`).

## Tier accuracy

| Decider | Test (my rows) | Blind holdout | Holdout normal / misleading | Missed Pro (holdout) | Latency |
| --- | --- | --- | --- | --- | --- |
| Codex Luna high (triage) | 97% | **90%** | 97% / 70% | 1/20 | 4.5 s |
| SemIf Qwen3.5-4B | 86% | **82%** | 93% / 50% | 3/20 | 0.02 s |
| Keyword rules | 95% | **57%** | 68% / 25% | 10/20 | 0 |
| CLM-8B zero-shot | 39% | 38% | 38% / 35% | 5/20 | 0.01 s |
| always "bounded" | 25% | 25% | | 20/20 | |

Keyword rules overfit to the author's wording: excellent on rows written by the same
author, poor on anyone else's. CLM zero-shot is not usable for this decision.

## Peer model (astra vs opus)

Easy decision: rules 100%, Codex 100%, SemIf 95%, CLM 70% on the holdout (20 rows).

## Combining with Codex triage (error cost per task, lower is better; asking the owner costs 1)

| Policy | Test: asked / cost | Holdout: asked / cost |
| --- | --- | --- |
| **Codex alone** | 0% / **0.03** | 0% / **0.19** |
| Codex + SemIf, ask on any disagreement (current) | 17% / 0.17 | 20% / 0.24 |
| Codex + SemIf, take higher tier if 1 apart, ask if 2+ | 0% / 0.08 | 6% / 0.21 |
| Codex + rules, ask on any disagreement | 8% / 0.08 | 42% / 0.46 |

The second voter does not pay for itself: it mostly adds owner pings or over-tiering
and did not rescue the one Pro case Codex missed. SemIf is the best local fallback
when Codex triage fails (timeout, quota, error): 82% at 20 ms on the owner's GPU.

## Limits

Labels come from Claude (main set) and a separate Opus run (holdout), not from the
owner; n is small (60 + 80). The real test is the owner's own tasks: every live
decision and owner pick is logged in the `decisions` table for re-evaluation.

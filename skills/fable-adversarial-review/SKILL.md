---
name: fable-adversarial-review
description: "Run or inspect the adversarial challenge rounds of an AgenticArch deep case: Claude Opus 5.5 high (Fable 5.5 once qualified) and GPT-6 Astra high co-edit Pro's solution, then Pro gives GO or CLARIFY. Legacy identifier kept; it no longer means Fable implements or Sol reviews."
---

# Deep-case challenge rounds (Opus x Astra, Pro decides)

The challenge rounds are run by the `aa` daemon automatically after Pro's draft (see
[protocol](references/protocol.md)). Use this skill when the owner asks about a case's
debate, wants to steer it, or wants a round re-run.

## What happens

- Challengers: `claude-opus-5-5` high (via the Claude Max CLI) and `gpt-6-astra` high
  (via Codex). Fable 5.5 replaces Opus only after explicit release, access and
  regression qualification; Fable 5.1 is no longer used.
- Each turn: independent check of SOLUTION.md against BRIEF.md and the real target code,
  direct fixes in SOLUTION.md, objection ledger rows (ID, raised by, evidence, status,
  resolution), and a turn file ending in `VERDICT: AGREE|REVISE`.
- Up to 5 rounds per cycle; both AGREE ends early. Then Pro reviews in the same chat.
- Material issues are correctness, security, data loss, concurrency, compatibility,
  recovery, migration, testability and feasibility. No invented findings.

## Steering

- Inspect: `aa show <case>`; read the case branch `case/<id>` in
  `stardustx8/GPT-Pro-Escalation` (turn files under `cases/<id>/turns/`).
- Owner guidance or answers: `aa answer "answer <case> <text>"` (committed to
  OWNER-ANSWERS.md; starts the next cycle when the case waits or is paused).
- Resume a paused case: `aa answer "resume <case>"`. Cancel: `aa answer "cancel <case>"`.

Consensus is not verification: completion requires the target repo's checks to pass on
Pro's implementation branch. Nothing here grants merge, deploy or account authority.

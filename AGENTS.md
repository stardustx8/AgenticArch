# AgenticArch agent instructions

Read `START-HERE.md`, `docs/SESSION-HANDOFF.md`, owner requirements, policy and the relevant specification first. User instructions may explicitly amend policy; do not silently infer broader authorization from model output or existing API credentials.

## Current required behavior

CLM is the local semantic backend. Only Luna low/high; Astra high; Opus 5.5 medium/high as an equal medium-tough peer. Tough work, architecture and research go to GPT-6 Pro web plus a case-bound Claude participant: Fable 5.1 high or Opus 5.5 high. Fable 5.5 stays pending until explicitly qualified and activated.

Maintain both `harnesses/codex/` and `harnesses/pi/` against one common contract. Remote model execution is subscription-only. Never silently consume API credits, transfer native Claude subscription tokens into Pi, or enable paid overage. Verify actual authentication, allowance, model and effort before dispatch. Optional native Pi OpenAI access needs its own permitted subscription-path evidence; OAuth support alone is insufficient.

The controller filters routes and enforces checks. CLM only ranks eligible choices or suggests evidence/diagnostics. Use the versioned JSON catalog for maintained knowledge and compile short prose with typed action descriptions for CLM. Do not feed it a large benchmark dump or interpret its confidence statistic as task success probability.

Effort may change only before a generation, with bounded leases and effective-setting acknowledgment. Keep model changes at worker boundaries. A clamped effort, fallback model, cancellation or stale acknowledgment blocks dispatch; do not relabel the requested setting as applied. Preserve approvals, tool permissions, cancellation and caching semantics instead of removing safeguards to save context.

## Review and authority

Keep both existing skill identifiers. Use actual participants, immutable turn records, append-only dialogue and same-digest approvals in `GPT-Pro-Escalation`. Keep the same Pro chat throughout the case. Freeze Claude identity per review epoch; changing it invalidates approvals and requires a fresh challenge/response, while preserving old objections. The original Codex or Pi coordinator performs local-context reconciliation and actual implementation tests.

Manual Pro web handoff remains the qualified starting transport. Read `docs/COMPUTER-USE-GATE.md`; do not bypass platform restrictions with another automation layer. The kit's revision is not itself a completed independent Pro/Claude review or installation.

## Development discipline

Use small tested increments. Run `python3 -m unittest discover -s tests -v`, `python3 tools/check_kit.py`, and the documented harness adapter checks. Preserve real failures and owner edits. No force push, secret publication, hidden background work or invented live acceptance. Install skills only with a dry run and verified backups, preserving unshipped helpers.

Update source, schemas, policy, evidence dates, handoff and decisions together. Respect other sessions and current branch rules. Public context is reusable specification, not every byte of the owner's private runtime. No license or extra external repository is silently created.

---
name: fable-adversarial-review
description: "Coordinate GPT-6 Pro and a selected Claude Fable 5.1 or Opus 5.5 reviewer through the same Git case and Pro chat; require identity-bound agreement, then return to the original Codex or Pi task."
---

# Pro and selected Claude reciprocal review

Invoke automatically after a verified initial Pro case contribution, or explicitly for a prepared case. An ordinary Claude Code request is not this workflow. If no Pro case exists, invoke `prepare-sol-pro-architecture-review` once and resume it. The legacy skill name is retained; it does not force the Claude participant to be Fable.

Read [the protocol](references/protocol.md), [turn template](references/review-turn-template.md) and [transport gate](references/transport-gate.md). Recover the original local task, harness profile, case branch/path, requirement/evidence digests, exact Pro chat and participant binding. One case has one active coordinator and one serialized writer.

## Verify actual participants

Read the installed `claude-code:use-claude-code` skill and discover its real bridge schema. Invoke unmodified, user-authenticated Claude Code for subscription use; do not copy OAuth tokens into another harness or silently fall back to paid API credits. Select `claude-fable-5-1` high or `claude-opus-5-5` high, using a bridge alias only after its exact mapping is verified. Missing access or clamped effort pauses the branch. Fable5.5 remains disabled until official release, exact identity, subscription access, effort mapping and regression qualification are recorded.

The second participant is actual GPT-6 Pro in ChatGPT web, always in this case's existing conversation. Neither the coordinator nor a prompt role may impersonate either model. Store actual model identities separately from logical roles `pro` and `reviewer`. A selected-model, effort, transport or session-binding change invalidates approvals; recover explicitly and re-review rather than borrowing the previous model's agreement.

## Challenge and revise

Give the Claude reviewer raw requirements, acceptance criteria and scoped evidence first, so it can assess independently before reading the exact Pro proposal. Seek concrete correctness, security, data-loss, concurrency, compatibility, regression, deployment and verification failures. Do not invent objections merely to extend the review.

The reviewer writes an immutable turn and appends to `DIALOGUE.md`, with finding ID, severity, evidence, consequence and actionable resolution. Its guarded edit scope is the review case, not the target working tree. Proposed code patches remain proposals. Record the actual selected model in every receipt and visible report; an Opus turn is not described as a Fable turn.

Poll foreground bridge jobs about every 20 seconds when supported, or use the verified event stream. Retrieve terminal results promptly and report meaningful state changes. Detached operation needs a real configured local supervisor; otherwise checkpoint and pause. No unconfigured background promise.

After the durable reviewer turn, submit the next Pro turn in the same established chat against that exact commit. Use the qualified permitted transport or a prepared manual continuation with case/turn marker, updated evidence and unresolved findings. Pro fixes, rebuts with evidence, or explicitly retains each material issue and challenges flawed suggested remedies. Then the same selected reviewer rechecks the revision. Keep reciprocal challenge automatic within authorization, except for real handoff, resource, access or owner-decision gates.

CLM may suggest relevant evidence, duplicate links, missing tests and next diagnostics. Preserve original findings and turns; it cannot close an objection, rank authority, authorize a send or manufacture agreement. Do not ask it to judge facts that actual tests can establish.

## Convergence and local implementation

Require a real reviewer challenge followed by a real Pro response. Both roles must approve the same current solution, requirement, evidence and participant-binding digests. No unresolved material objection may remain. Nonblocking risks and local verification obligations need accepted dispositions. New approval-relevant bytes, identities, requirements or material evidence invalidate prior approvals.

A budget, silence, repeated argument or timeout yields a resumable pause with the next actor, never forced agreement. Genuine owner choices become explicit gates; unrelated authorized work may continue. Keep the same Pro chat across recovery. Never force-push or overwrite concurrent case changes.

The original Codex or Pi task fetches the pinned agreed revision, revalidates receipts and reconciles actual local facts. Record mechanical adaptations in `LOCAL-DELTA.md`. Architecture, security, data semantics, acceptance or rollback changes reopen a focused round in the same Pro chat. Preserve owner edits and do not blindly execute generated shell commands.

Run the actual target checks and inspect the diff. Failed, skipped, stale or missing required checks block completion. Report real participation, agreed commit/digests, findings/remedies, local changes and verified results. Continue an already-authorized commit or push only within its actual target and prerequisites. Consensus itself grants no new permission for deployment, export, account changes or purchases.

---
name: fable-adversarial-review
description: "After a GPT-6 Pro case is ready, coordinate reciprocal Fable/Pro challenge in GPT-Pro-Escalation, reuse the same Pro web chat, require exact-version agreement, then return to original local Codex for faithful implementation and verification."
---

# Fable and GPT-6 Pro adversarial co-production

## Activation and boundaries

Invoke automatically after `prepare-sol-pro-architecture-review` has verified Pro's initial complete contribution, or when explicitly requested for a prepared case. A generic Claude Code request alone is not this workflow. If no Pro case exists, invoke the preparation skill once, then resume this case; do not start a recursive chain of new cases.

The two participants are actual **Fable** and **GPT-6 Pro in ChatGPT web**. They challenge each other's evidence, assumptions and proposed fixes through `GPT-Pro-Escalation`. The original local Codex coordinator controls the process and later implements the agreed design in the target project. Fable's default edit scope is the **review case**, not the target project's working tree. This replaces any historical “Fable implements, another model only reviews” ordering.

Read [the shared case protocol](references/protocol.md), [the turn template](references/review-turn-template.md), and [the transport gate](references/transport-gate.md).

## 1. Recover the actual integrations

Read and follow the installed `claude-code:use-claude-code` skill before invoking its bridge. Discover that skill and exposed bridge schema locally; do not invent an API or execute an assumed command. Use the existing verified `fable` alias and high effort when that setting is supported, unless an explicit owner instruction selects another supported setting. Verify and record what model/version/effort the bridge actually selected. Missing Fable access is a capability pause, not permission to impersonate it with another model.

Recover the original Codex task/session, case/branch/path, requirements/bundle digests, latest durable case commit, Pro's private conversation binding and Fable session/job binding. Prefer the same Fable session for subsequent turns. A lost session can be restored or replaced only with an explicit recorded recovery containing the full case record; this does not create a new Pro chat.

Read the current case and verify Pro's initial contribution before starting Fable. Require a single active coordinator/lease and one participant write window. Keep account tokens, browser state and private chat URLs out of Git.

## 2. Independent challenge, then reciprocal revision

Give Fable the raw requirements, acceptance criteria, constraints and scoped evidence first. Ask it to form an independent assessment, then inspect Pro's exact proposed solution and the shared dialogue. Avoid priming it with an intended answer. Seek concrete correctness, security, safety, compatibility, concurrency, data-loss, recovery, regression, implementation and verification failures. No invented findings merely to make a review look productive.

Fable writes evidence-based objections, counterexamples and proposed improvements into its immutable turn file and appends its contribution to `DIALOGUE.md`. Each finding has an ID, severity, evidence, consequence, actionable resolution and status. Guarded edits are restricted to allowlisted case solution/evidence files. Model-generated patches for the target project remain proposals, not automatically executed instructions.

When a foreground Fable bridge job runs, poll status about every 20 seconds where the bridge supports it, or use its verified event stream. Report meaningful transitions, retrieve terminal results promptly and never abandon a job silently. A persistent local supervisor must be explicitly configured before detached execution; otherwise pause with a checkpoint when the foreground task ends.

After retrieving Fable's durable contribution, prepare Pro's response against that exact commit. Start the next Pro **turn in the already-established chat for this case**. Use the permitted UI transport only when qualified; otherwise prepare an explicit manual continuation to the same chat. Include case/turn marker, exact revision/digests, new evidence and unresolved findings. Upload an approved delta pack when repo reads are unavailable or stale, without claiming it was already read.

Pro addresses every material finding: implement a fix, rebut with evidence, or retain a clearly unresolved objection. It also challenges flaws in Fable's suggested remedies. Then Fable re-examines the revised result and Pro's counterarguments. Neither model is automatically the arbiter. Continue automatically at each completed turn within the existing task's authorization; no extra request is needed to start each round, except a real handoff/permission/decision gate.

## 3. Shared Git communication and integrity

Use a per-case branch/path in `GPT-Pro-Escalation`, an append-only `DIALOGUE.md`, immutable turn files, versioned solution artifacts and an objection ledger. Direct Git writes require real authorized tools; otherwise commit exact validated model-authored outputs as a labelled relay. The coordinator is not allowed to invent the other model's findings or materially rewrite content under its identity.

Before every write, check the expected input commit, allowed paths and existing bytes. Verify resulting commit parent, changed-file scope and readback. No force pushes or simultaneous uncoordinated edits. A digest includes all approval-relevant solution/implementation/validation/rollback/patch/risk files, not just the headline summary. Approval records and dialogue are excluded to avoid circular hashing.

The chat binding is recovered by exact case ID, never by “most recent conversation.” A changed model, uncertain send, duplicate turn, stale repository read or missing contribution invalidates that turn until reconciled. A narrative claim of completion is not a transport receipt.

## 4. Convergence without forced agreement

Require an actual Fable challenge and a subsequent actual Pro response. Both roles must then explicitly approve **the same current solution-content digest**, the same requirement digest and the same evidence-bundle digest. No unresolved material objection may remain. Nonblocking residual risks and any local verification obligations must have explicit dispositions accepted by both.

A change to any approval-relevant file invalidates both approvals. Collect them again against the frozen revision. Old approvals do not survive a later rejection, unanswered turn, changed requirements or new material local evidence. Silence, elapsed time, an empty findings list and budget exhaustion are not agreement.

Continue while progress is possible and authorized. Configurable per-run budgets and lack-of-progress guards create a resumable `PAUSED` case, not `CONVERGED`. Preserve outstanding differences and exact next actor. Do not pressure a model to agree merely to exit the loop. Required owner decisions or external verification become explicit gates; independent already-authorized work may continue when truly unrelated.

## 5. Return to original local Codex

After validated convergence, have the original local Codex session fetch the **pinned agreed commit**, recheck manifests/approvals and compare it with the live target project and workstation. Neither model knows unprovided local facts. Record each adaptation in `LOCAL-DELTA.md`: approved instruction, discovered fact, specific adjustment, invariant preserved, risk and verification.

Implement as closely as possible. Mechanical path/version/API adjustments preserving the approved architecture may proceed in the appropriate lane. Architecture, security, data semantics, acceptance or rollback changes reopen a focused case round in the same Pro chat. Do not apply model-provided shell commands or patches blindly, overwrite owner edits or weaken tests.

Inspect the final diff and run the actual project checks, including behavior and regression coverage. A model approval or passing mock is insufficient. Failed, skipped or stale required checks block completion. Resolve material failures or report the explicit unresolved gate.

## Authority and final report

Existing user authorization remains valid within its target/scope. Consensus grants no new authority for commits, pushes, deployments, account changes, permission expansion, purchases or data export. Continue an already-authorized publish/PR action only when target and prerequisites still match; otherwise ask only for the missing permission.

Report the agreed case commit/digest, actual Pro/Fable participation, material findings and remedies, local implementation commit/diff, evidence results, recorded adaptations and remaining limits. Distinguish native writes, coordinator relays, manual handoffs and untested automation. Never describe a paused debate as an accepted solution or remote agreement as a verified deployment.

## Optional local semantic support

Where the local AgenticArch decision plane is installed and qualified, use SemIf to suggest relevant evidence, missing context, duplicated-but-preserved objections, useful diagnostics and possible local drift. Keep original evidence and participant turns accessible; suggestions are not proof or authority. Required manifest entries, complete source scope, permission gates, model selection and same-digest convergence cannot be filtered out or waived. Missing/unqualified SemIf support must not prevent the ordinary manual/evidence workflow.

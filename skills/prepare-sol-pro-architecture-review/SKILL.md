---
name: prepare-sol-pro-architecture-review
description: "Escalate tough problems, architecture and research to GPT-6 Pro in ChatGPT web: build a scoped evidence ZIP and prompt, coordinate a permitted handoff into GPT-Pro-Escalation, then activate fable-adversarial-review. Keep this exact identifier for compatibility."
---

# Prepare and hand off a GPT-6 Pro review

## Outcome and activation

Use this skill for tough work, architecture-level decisions, research, consequential implementation plans, or an explicit invocation. Produce a complete evidence pack and a final, challengeable Pro solution in `GPT-Pro-Escalation`, then hand the case to `fable-adversarial-review`. This is not an instruction to select the historical model named in this skill's identifier.

Required reviewer: **GPT-6 Pro in the ChatGPT web interface**, with the actual visible Pro selection verified. Ordinary Astra at high/max, an API model, or an agent role labelled “Pro” is not a substitute. Only an explicit owner policy change may select a different reviewer/transport. Keep runtime model controls outside the task prompt. Use current official guidance for the selected product; do not treat a moving model page or the model's self-description as identity evidence.

Read [the shared case protocol](references/protocol.md), [the handoff template](references/handoff-template.md), and [the transport gate](references/transport-gate.md). These references are self-contained and ship with the skill.

## 1. Recover or initialize the case

Record the original local Codex task/session, target repository, requested outcome, acceptance criteria, exclusions, constraints, permission scope and observed baseline. Preserve owner edits. Reuse an existing case when this is a continuation; never create another chat merely because a process restarted.

Use the repository named `GPT-Pro-Escalation`, one `case/<case-id>` branch and `cases/<case-id>/` path. Repository creation, privacy settings, pushes and exports need the applicable existing authorization; the repository name alone grants none. Prefer private visibility for real cases. Verify the actual Git write path with readback, not only a permission flag. If creation/access is blocked, prepare the local artifacts, checkpoint the missing action and do not claim a remote contribution.

## 2. Build the evidence package

Inventory every in-scope component and supplied artifact. Read primary material in full when completeness matters. Cover model/tool versions, topology, lifecycle, configuration, dependencies, previous attempts, relevant code and tests, deployment constraints, and unknown local facts. Do not imply that unreviewed material was read.

Keep the manifest compact and separate:

- direct observations, including commands and exact source revisions;
- owner-stated requirements and environment facts;
- current primary-source facts with citations;
- candidate plans and prior reviewer conclusions, which remain challengeable;
- inference, omissions, redactions and unresolved decisions.

Use explicit source-path allowlists and a stable snapshot including relevant dirty changes. Remove credentials, recovery values, unique device identifiers, unrelated files, personal/customer data and unnecessary internal topology. Reject traversal, symlinks and special files. Avoid copying opaque binaries or oversized logs without an explicit need. Local SemIf or local models may help find relevant evidence; their summaries do not replace exact sources and cannot approve export.

Create `context.zip`, `PROMPT.md`, `MANIFEST.json` and a short private runtime record. The manifest names every attachment exactly, records included-file hashes and source classes, and declares what is missing. Hash the completed ZIP separately; do not include its own hash inside itself. Bind export approval to actual bytes, destination and data scope. Never put browser profiles, tokens or private conversation URLs in the ZIP or public repository.

## 3. Write the review contract

Use the handoff template. Ask for the complete final solution and implementation/validation plan, not only criticism. Candidate plans may be replaced with materially better alternatives. Require sourced checks for unstable claims, local-versus-remote evidence labels, concise decision/risk records, acceptance coverage and explicit branches for unresolved owner choices.

Give Pro freedom to choose the analysis. Do not request hidden chain-of-thought, a fixed number of objections, or an arbitrary number of iterations. Preserve safety/privacy/authorization boundaries once. Design work does not authorize live configuration changes or implementation beyond the task's existing permissions.

Resolve all placeholders and explicitly instruct Pro to work in the named review repository, branch and case path. A direct Git contribution is preferred **only if that chat actually has authorized write-capable tools**. Otherwise ask for exact downloadable files for a labelled coordinator relay. Do not present a relay as a Pro-authored Git push.

## 4. Submit or prepare manual transfer

First inspect the transport gate. The standard Computer Use documentation currently excludes automating ChatGPT itself. Do not bypass that restriction with another tool, browser, endpoint, local model or permission change.

When the exact workflow has a documented, explicitly permitted, locally verified automation capability, use Codex's exposed Computer Use integration: verify origin/account and visible Pro selection, create the outbox record, attach the approved ZIP, wait for readiness, submit the resolved prompt once, confirm its case/turn marker and persist the exact conversation binding privately. Observe actual UI state; do not invent selectors or tool calls.

Otherwise deliver the ready ZIP/prompt and attachment list for **manual** Pro web transfer, enter `WAIT_MANUAL_TRANSFER`, and request only the missing handoff action. For an existing case, target its already-bound chat. Do not claim automatic submission, silently use an API model or fabricate a response. An entirely unattended requirement remains blocked until the transport is qualified.

## 5. Verify completion and activate Fable

Monitor only through a real available foreground tool or configured local supervisor. Check meaningful lifecycle changes; never promise unconfigured background work. Reconcile uncertain sends before retrying. Respect rate limits, expired sessions, cancellation and platform prompts; preserve the same case/chat across a pause.

When Pro completes, retrieve the actual result. Validate the expected case/turn, input digests, allowed file paths, all required deliverables, citations/evidence status and durable repository contribution (native or labelled relay). A stopped spinner or “done” message is insufficient. Record the role/transport receipt and output commit.

Then **invoke `fable-adversarial-review` automatically** with that case, original task binding, Pro chat binding and exact input commit. Do not ask the owner to start the challenge again when already authorized. This skill stops at the handoff to the challenge coordinator; it must not recursively reinitialize itself on every Pro continuation.

## Validation and delivery

Verify exact attachment names and hashes, complete requirement/component coverage, no secrets or unrelated material, correct Pro target, explicit unknowns, working local reference links, nonconflicting permissions and an implementation-ready requested outcome. Report produced files, actual handoff mode, durable commit or pending transfer, and the next actor. Never claim model review, upload, push or skill installation without an actual receipt.

For reusable/high-risk changes, forward-test with independent scoped agents and raw synthetic evidence. Give them only the permissions needed to write review-case artifacts, not to modify the target project or live machine. Offline fixture success is not an independent model review or a live integration test.

## Optional local semantic support

Where the local AgenticArch decision plane is installed and qualified, use SemIf to suggest relevant evidence, missing context, duplicated-but-preserved objections, useful diagnostics and possible local drift. Keep original evidence and participant turns accessible; suggestions are not proof or authority. Required manifest entries, complete source scope, permission gates, model selection and same-digest convergence cannot be filtered out or waived. Missing/unqualified SemIf support must not prevent the ordinary manual/evidence workflow.

# Pro–Fable escalation protocol

This protocol applies to tough work, architecture, research, and consequential design. Its outcome is an agreed, versioned solution that the original local Codex session can implement. It is not remote proof that the local software works.

## 1. Identities, repositories, and branches

Create an opaque case ID such as `case-20260924-a1b2c3d4`. Do not derive a public identifier from a customer's name or confidential issue. Store review work under `cases/<case-id>/` on branch `case/<case-id>` in the configured `GPT-Pro-Escalation` repository. Bootstrap its generic default-branch templates only when creation/writes are authorized; preserve existing content and visibility. Do not merge every debate turn into the target project's `main`.

Keep the original local task/session ID, target-project locator, target baseline, bundle digest, requirements digest, and authorized export destinations in local state. Bind **one ChatGPT conversation to one case**. Store its exact canonical URL and conversation identity privately, not in AgenticArch or a public case document. Every subsequent Pro round must use this conversation. A new round means a new message, not a new chat.

Fable uses the real local skill's configured provider/model/session mechanism. Record its effective identity; do not assume an approximate skill name proves a particular model version. The coordinator may relay, but must never write both model approvals itself as a substitute for invoking both participants.

## 2. Case files

```text
cases/<case-id>/
  case.json                    sanitized case metadata and current protocol status
  BRIEF.md                     goal, constraints, acceptance criteria, unknowns
  CONTEXT-MANIFEST.json        exported files, hashes, redactions and omissions
  DIALOGUE.md                  append-only shared communication document
  SOLUTION.md                  current co-produced solution
  VALIDATION.md                evidence, citations, counterexamples and unrun checks
  IMPLEMENTATION.md            steps, files/contracts, tests, rollback
  objections.json             stable finding IDs, severity and disposition
  solution-manifest.json      exact solution file set and hashes
  reviews/<turn-id>.json       role-specific review and transport receipt reference
  turns/<turn-id>.md           immutable authored turn record
  patches/                    optional target-project patches, never auto-executed
  LOCAL-DELTA.md               post-convergence local reconciliation
```

This is the runtime layout to implement. The kit supplies starter templates, not a fabricated completed case. Large context ZIPs can remain local and be uploaded only to approved model destinations; the repository manifest records their digest and omissions. A copy in the private review repository is optional and separately covered by the export policy.

`case.json` is a repository-facing record, not a place for chat URLs or credentials. The local database is the controller's execution authority; committed case files are the shared review record. Restart recovery reconciles both against actual Git and browser receipts rather than trusting either one blindly.

## 3. Context pack

`prepare-sol-pro-architecture-review` captures the user request, acceptance criteria, constraints, relevant source files, exact baseline, dirty diff, failing/passing commands, dependency/tool versions, previous attempts, alternatives tried, local capabilities, deployment constraints, and unresolved questions. Include enough concrete context for an implementable answer, not an indiscriminate home-directory export.

Use an explicit path allowlist and inventory. Redact secrets, personal/customer data, browser state, tokens, private endpoints, unrelated code, and sensitive logs. Reject symlinks, path traversal, special files, oversized files, and opaque binaries unless specifically approved. Record redactions and omissions so reviewers know what they cannot see. A scanner is only one check; export approval is tied to the actual file list, destination, and content digests. Changed bytes invalidate the approval.

Create a reproducible ZIP and separate UTF-8 prompt. Hash the exact ZIP bytes after construction; distinguish that transport digest from the digest of the source snapshot and from the solution-content digest. Never put a ZIP's own checksum inside itself as if it could be self-consistent.

## 4. First Pro turn

**Current default:** manual Pro web handoff. Standard Computer Use excludes automating ChatGPT itself. Apply `docs/COMPUTER-USE-GATE.md` before using any automatic UI steps described below; do not bypass that restriction. Manual rounds retain exact case/chat binding and labelled human transfer receipts.

Use `prompts/PRO-FIRST-TURN.md`, with all placeholders resolved and the correct case/repository/branch supplied. When the exact automation path is permitted and qualified, through Codex Computer Use inspect the authenticated browser, verify the ChatGPT origin/account and the **GPT-6 Pro** selection, attach the approved ZIP, wait for attachment readiness, and submit the exact prompt once. Verify message appearance and persist the conversation binding immediately.

Tell Pro to work in `GPT-Pro-Escalation`, within the case path and branch. It must produce the solution, implementation instructions, validation/evidence, risks, and open questions, and append its initial contribution to `DIALOGUE.md`. Direct repository writes are preferred only when a write-capable Git tool is actually exposed and authorized in that chat. Otherwise request downloadable files/patches and have the coordinator commit them unchanged after schema/path/export validation. Mark transport as `relayed`; do not claim Pro directly pushed.

The coordinator verifies the resulting commit and file contents. Browser text saying “done” or a stopped spinner is insufficient. Pro is finished with the initial phase only when a complete contribution and end-of-turn receipt exist for the expected case/input. Then invoke `fable-adversarial-review` automatically.

## 5. Alternating adversarial turns

Fable first reads the brief and criteria and records an independent assessment of likely failure modes before accepting Pro's framing. It then inspects the actual solution, code or patches, evidence, and assumptions. It must seek concrete counterexamples, alternatives, failure/recovery cases, security problems, missing acceptance coverage, and unnecessary complexity. Valid concerns receive stable IDs and severity; criticism must be testable or tied to evidence.

Pro reads Fable's committed turn and responds **in the same established ChatGPT conversation**. The continuation prompt contains the case ID, turn ID, exact branch/input commit and content digests, outstanding objections, and where to read the authoritative files. If Git reads are unavailable or stale, upload a fresh approved delta pack into that same chat. Pro addresses every blocking objection by accepting and fixing it, rebutting it with evidence, or explicitly recording an unresolved disagreement. It also challenges weaknesses in Fable's proposed changes.

Fable then reviews the resulting revision, including Pro's counterarguments. Continue in this alternating pattern. Do not count rhetorical agreement, silence, absence of new findings, or elapsed time as approval. A reviewer may say no. The objective is a defensible solution, not agreement at any cost.

`DIALOGUE.md` is append-only: turn ID, role, input revision, proposed/approved solution digest, addressed objection IDs, evidence references, verdict, and next actor. Keep concise reasons and inspectable evidence, not demands for hidden chain-of-thought. Immutable per-turn files preserve recovery and provenance.

## 6. Writers, commits, and transport modes

One coordinator holds the case execution lease and permits only one active participant write window. Use two supported modes, selected by capability discovery:

- **Native Git mode:** the active participant reads the exact base and writes only the allowlisted case files. Verify the commit, parent, changed paths, and contribution identity before the next actor starts.
- **Relay mode:** the model authors files/patches; the coordinator validates and commits them, preserving exact content and recording the model role separately from the Git committer. The coordinator must not invent or materially rewrite the review under that model's identity.

Every commit is based on the expected parent. A normal non-force Git push rejects competing non-fast-forward history. On a conflict, fetch and reconcile; never overwrite the other participant. A local lease alone does not lock GitHub for another host, so MVP supports one coordinator host per case. Cross-host leases need a separate reviewed design.

Record an outbox item before upload/send/commit, including case, turn ID, input digest, destination, and idempotency key. Record the actual receipt afterward. On restart between those steps, first inspect the existing message/commit and reconcile it. Browser operations cannot promise exactly-once delivery: an ambiguous send becomes `WAIT_HUMAN` rather than a blind duplicate. A duplicate case/turn marker is rejected by the receiver/coordinator.

## 7. Exact convergence

The solution digest is a SHA-256 over canonical JSON containing the schema version and a sorted list of `{path, sha256}` for the approved solution files. Include the plan, solution, proposed patches, acceptance/rollback instructions, `objections.json` with residual-risk dispositions, and evidence material they rely on. Exclude transport metadata, the evolving dialogue, approval records, and the manifest file itself to avoid circular hashing. `reference/core.py` implements a simple content-manifest digest helper; production also validates the export/path/snapshot contracts.

Convergence requires all of these:

1. At least one actual Fable challenge and a Pro response occurred; transport receipts identify both real invocations.
2. The current solution files recompute to the declared digest. Both roles explicitly return `APPROVE` for **that exact digest**, the same requirements digest, and the same input-bundle digest.
3. No open critical/high or otherwise release-blocking objection remains. Residual nonblocking risks have explicit dispositions accepted by both; they are not silently deleted or downgraded.
4. Evidence references are real, relevant, and available at the cited revisions. Unrun remote checks and unknown local facts are explicitly identified; local validation obligations are complete enough to execute.
5. Required plan sections and acceptance criteria are covered, and neither model's contribution is awaiting an uncommitted edit or an unnormalized verdict. A later turn without a verdict invalidates use of that role's earlier approval until reconciled.

Any approved solution-file change invalidates both approvals for that solution. If Pro approves revision B and Fable approves revision C, the case has not converged. Use `schemas/convergence.schema.json` for the normalized approval record, plus semantic checks; JSON schema alone cannot establish real model participation or correctness.

## 8. Budgets and pauses

Defaults: at most six full Fable/Pro rounds per run; pause for review after two consecutive rounds with no substantive change and unresolved objections. Persist cumulative rounds across resumes. These guards prevent uncontrolled looping without redefining agreement. An owner-authorized resume can continue the same case and chat with a renewed budget; it must not discard history or imply that convergence is inevitable.

Rate limits, expired login, upload limits, blocked automation, missing Fable access, or a missing model -> explicit pause with a checkpoint. Do not evade anti-bot controls, create replacement accounts/chats to escape limits, or silently use a different model. Never run the debate detached without a configured local supervisor and cancellation path.

## 9. Return to local implementation

Fetch the pinned solution revision and validate both approvals and manifest locally. Do not implement whatever currently happens to be at the branch tip. Reconcile target HEAD, owner edits, versions, platform, filesystem, installed services, permissions, and deployment facts against the submitted baseline.

Document each adaptation in `LOCAL-DELTA.md`: approved instruction; newly discovered local fact; exact change; preserved invariant; risk; verification; escalation decision. Mechanical path/version/API adjustments that preserve the agreed design may proceed in the appropriate coding lane. Changes to architecture, security, data semantics, acceptance criteria, or rollback guarantees reopen focused Pro/Fable review in the same case/chat.

Implement incrementally in the target project. Do not blindly apply model patches or overwrite owner edits. Re-run actual project tests and behavior checks after adaptation. Publish a final report with target commit/diff, verification evidence, agreed case revision, documented deviations, and remaining limitations. Close the case only after this local gate, not at remote convergence.

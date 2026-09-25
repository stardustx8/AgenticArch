# Pro and selected-Claude case protocol

Version 2. The original local coordinator may be Codex or Pi. The deep anchor is actual GPT-6 Pro in ChatGPT web; the second role, `claude`, is bound to `claude-fable-5-1` or `claude-opus-5-5`, at high effort. The exact skill identifier `fable-adversarial-review` is retained for compatibility and does not force the Fable model.

## Identity and storage

Use `GPT-Pro-Escalation`, one `case/<case-id>` branch and `cases/<case-id>/` directory. Keep task/session IDs, exact Pro chat binding, Claude worker binding and auth state in private coordinator storage. Use one active coordinator and one serialized writer for the case. Repository name alone does not grant write or export permission.

The case record binds requirements, evidence-bundle and solution digests; a review epoch; selected Claude model; original task/harness; permitted operations; and the accepted input Git commit. Credentials, browser profiles and private chat URLs do not enter a public repository or model bundle.

## Artifacts and contribution

A case contains BRIEF, input manifest, SOLUTION, IMPLEMENTATION, VALIDATION/rollback, objection ledger, append-only DIALOGUE, immutable turn files, solution manifest and transport receipts. Each turn states case, epoch, role, observed model/effort, input commit/digests, output paths and next actor. Native Git writes require real authorized tools. Otherwise relay exact validated model-authored files and label the transport as a coordinator relay; never impersonate the other participant.

Before writing, verify expected parent and allowed paths. Read back output bytes and commit. No force push, concurrent overwrite, symlink traversal or executable instructions accepted solely because they came from a model. Lock the solution manifest's explicit paths and hashes, including patches, risks and validation/rollback artifacts. Exclude approvals, receipts and dialogue from solution hashing to avoid circularity.

## Initial Pro handoff

Package scoped evidence with observed state, owner requirements, current primary-source facts, candidate plans, inferences and omissions clearly separated. Read complete primary material where coverage matters. Redact secrets and unrelated data, preserve exact attachment names and hashes, and bind export approval to the actual bundle/destination. Ask for a complete revised solution, not only critique. Candidate plans remain challengeable. Carry unavailable owner choices as explicit branches, not invented requirements.

Select the actual visible Pro product; an API model, self-description or role label is not a substitute. Persist a send marker before submission, then verify receipt and exact case-to-chat binding. Use manual ZIP/prompt transfer while automatic web transport is unqualified. On an uncertain send, reconcile the existing chat before retrying. Never start another chat simply because a process restarted.

A complete durable Pro contribution, not a stopped spinner, activates `fable-adversarial-review`. Do not require another owner prompt when this continuation is already authorized.

## Reciprocal challenge

Give the selected Claude worker raw requirements and evidence before Pro's proposed answer, supporting independent assessment. Then expose the exact solution and dialogue. Require concrete correctness, compatibility, security, concurrency, data-loss, recovery, regression and implementation findings. Do not invent objections to fill a quota.

Claude may edit the scoped case artifacts and propose patches, not silently edit the target project's working tree. Pro responds in the same established chat to the exact new commit: fix, rebut with evidence or leave the objection unresolved. Pro also challenges flawed remedies. Repeat while material issues remain and progress is possible. Preserve each original finding and disposition; CLM can suggest links or evidence but cannot suppress findings or declare agreement.

Poll actual foreground workers or use a configured supervisor/event stream. Retrieve completion, failure or attention requests promptly. No unconfigured background promises. Respect cancellation, rate limits, user decisions, manual handoffs and unavailable tools. A finite per-run budget produces PAUSED with the exact next actor, not CONVERGED.

## Participant changes and review epochs

Freeze the Claude model per epoch. A deliberate switch between Fable and Opus, a future activated successor, or an identity/configuration change starts a new epoch and invalidates both approvals. Preserve prior dialogue and carry every unresolved material objection forward. Keep the same case and Pro chat. Require a fresh actual Claude challenge and subsequent Pro response in the new epoch. Historical receipts remain auditable but cannot approve current content.

`CaseReview` validates the current epoch while allowing historical receipts to remain. Its input projection must retain open blockers from earlier epochs. The validator cannot prove completeness of that projection; the coordinator must reconcile the full objection ledger and cannot delegate that authority to CLM.

## Convergence

Both actual roles must explicitly approve the same solution, requirements and bundle digests in the current epoch, with matching observed participant identities. Require a real Claude challenge followed by a real Pro response, complete manifests/deliverables, verified evidence references and no unresolved material objection. Later rejection, unanswered contribution or an approval-relevant change invalidates earlier approval. Minor residual risks require explicit agreed dispositions in hashed content.

Silence, a budget timeout, score thresholds, an empty findings list or agreement produced by one model playing two roles is not convergence. Consensus is not correctness or permission for new external actions.

## Local implementation and closeout

The original coordinator fetches the pinned accepted commit, validates digests/receipts and compares it with the actual target project. Record each local adaptation in LOCAL-DELTA with the new fact, preserved invariant, adjustment, risk and check. Mechanical adaptations may proceed within scope. Architecture, security, data semantics, acceptance or rollback changes reopen focused review in the same Pro chat.

Implement faithfully, inspect the actual diff and run required checks against the current snapshot. Model agreement and offline fixtures cannot substitute for those checks. Report accepted case commit, real participants, findings/remedies, local implementation changes, actual test results, adaptations and remaining gates. Continue existing authorized publication only within its target/scope; never let consensus grant new permissions.

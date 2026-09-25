# Adapter contracts

## Common job envelope

Bind every job to task/session, selected harness, optional case/epoch/turn, input snapshot, requirements and check-plan digests, allowed paths, operations, deadline/cancellation and budget. Record actual model/effort/auth method and transport receipts. These facts come from trusted adapters, not model-authored fields. Revalidate before dispatch, preserve owner edits and store detailed runtime records privately.

The common result distinguishes completed, failed, cancelled, pending, unknown-send, capability-blocked and quota-exhausted states. Unknown is not a retry authorization. Persistent outbox identity and actual receipts resolve duplicate sends. No implicit API or provider fallback.

## Model workers

Use each harness's real supported interfaces. The Codex profile binds native subscription workers; the Pi profile can use those workers or a separately qualified native OpenAI subscription route. Preserve tool schemas, required reasoning settings, sandbox controls, cancellation and original-task identity. Read back effective settings; missing or clamped controls do not count as applied.

Claude work uses the installed claude-code:use-claude-code bridge and an unmodified native worker. Select the exact qualified claude-fable-5-1 or claude-opus-5-5 identity, not a guessed alias. Use high effort for deep review, medium/high as selected for ordinary Opus work. No imported Claude OAuth tokens or silent paid overflow. If dynamic effort is unavailable, hold the current worker's fixed effort and change only on a safe later worker boundary.

## CLM

Follow [the CLM contract](CLM-ADAPTER.md). The local HTTP client uses a typed choice request, exact tokenizer limits, pinned deployment checks and strict scores/model/options validation. The model provides suggestions only. Use the normalized generic operator interface separately from upstream wire shape. No tool commands, privileged paths, permission flags or final approval are learned outputs.

## Effort checkpoint

A native host captures context after accepted user input/tool results, obtains a bounded decision, applies it under its settings owner, captures effective model/effort, acknowledges and only then permits sampling. Lease invalidation and manual priority are mandatory. A frontend wrapper that merely edits prompt text cannot claim this contract. Pi callback exceptions need explicit abort and real no-request acceptance.

## Pro transport and Git review

Follow [the transport gate](COMPUTER-USE-GATE.md). Manual transfer is current default. A Pro chat must actually have write tools before native Git contribution is claimed; otherwise preserve exact returned files via a labelled relay. Keep private chat/session bindings outside Git. Compare expected parent, allowed changes and actual readback for every write. New reviewer identity starts a new epoch, not a silent edit to old approvals.

## Verification and quota

Run approved argv under controlled environment, worktree, timeout and cancellation, without shell-interpolating model text. Detect changed snapshots during checks, preserve failed/skipped results and require actual behavioral evidence. Quota observers report provider/bucket/window/units and measurement precision/time. Unknown or concurrent deltas are not attributable; API-equivalent dollars remain diagnostics only.

## Stateful runtime

Use one coordinator lease and transactional task/case state with an outbox. The reference modules intentionally do not implement the whole persistent supervisor. Production integration must prove crash consistency, uncertain-send reconciliation, permission enforcement and request blocking. A schema or a boolean marked true does not authenticate itself.

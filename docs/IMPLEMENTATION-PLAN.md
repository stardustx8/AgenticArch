# Implementation plan

## Phase 0: inventory and protect the working setup

Read the current requirements, handoff and selected harness package. Verify actual repository head/worktree, installed client revisions, exact skill paths and unshipped helpers, local GPU/runtime, CLM availability, model catalog, subscription login and quota observers. Inspect names/status without exposing credential values. Keep detailed inventory private and publish only a sanitized capability matrix.

Do not replace a working client globally. Create a separate profile/build and backup the actual skill files using the existing dry-run-first installer. Qualify exact interfaces instead of inventing command flags or model aliases.

## Phase 1: shared deterministic loop

Integrate `reference/core.py` and `reference/routing.py` into one coordinator with persistent task state, transaction/outbox, explicit scope, immutable snapshots and real check results. Use fixed defaults and one qualified subscription worker first. Test cancellation, restart, failed checks, stale evidence, denied billing and concurrent source changes. No model may write its own permission/identity receipts.

## Phase 2: CLM migration

Retire the old backend from active config without deleting unrelated local installations. Pin encoder/tokenizer/pooling/head/server configuration. Bind both services to loopback and disallow unsolicited downloads, CORS and shared UI exposure. Supply the exact tokenizer and trusted deployment observer to `reference/clm.py`. Test overflow, schema mismatch, invalid probabilities, changed weights and unavailable encoder before any advisory routing.

Run task/effort and the nine evidence operators in shadow mode. Build task/project/time-disjoint evaluations; do not inherit old calibration. Activate one operator at a time only when it improves the real workflow while preserving quality and authority boundaries.

## Phase 3: harness profiles and adaptive effort

For custom Codex, port a native pre-generation checkpoint to the actual fork and preserve provider connection/history/security. Connect the host adapter and bounded effort gate under the native sampling lock. For Pi, connect the supplied structural adapter to observed session/effort surfaces and a bounded local decision source. Prove cancellation prevents a provider call. Delegated Pi workers use the native worker's checkpoint.

Keep an explicit fixed-effort fallback for a missing adaptive surface; do not claim dynamic operation. Native Pi provider access is enabled only with supported subscription/auth evidence. Claude remains unmodified Claude Code. Verify no API keys or paid overflow were used.

## Phase 4: expanded deep review

Install the exact-name revised skills, preserving helper trees. Bind the case's Pro chat and selected Claude model, use immutable turns and the shared dialogue, and authenticate all receipts. Keep manual Pro transfer until automation is permitted and tested. Demonstrate real Pro/Claude challenge, same-digest approval, participant-change invalidation, resource pause/resume and faithful original-coordinator implementation. Synthetic receipts do not satisfy this phase.

## Phase 5: compare and promote

Run the controlled subscription evaluation across both harness profiles and selected efforts. Include failed attempts, human intervention, quota precision/reset/concurrency and actual checks. Compare native and delegated Pi separately. Choose configurations from measured quality/resource trade-offs, not a social headline or mixed-effort vendor leaderboard.

Promote route/effort decisions only after held-out workload qualification. Future Fable activation needs exact release/access/settings evidence and regression testing. Keep rollback immediate: fixed defaults, deterministic selection, old client profile, private state preserved.

## Closeout

Update source, schemas, model evidence, implementation status, decisions and session handoff together. Run all offline tests and relevant live scenarios; mark every unexecuted live check NOT_RUN. Publish ordinary commits to main after reconciling concurrent work and read back the actual resulting tree. No forced history rewrite, speculative deployment success or unconfigured background monitoring.

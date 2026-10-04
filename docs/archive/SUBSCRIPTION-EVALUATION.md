# Subscription-aware evaluation

The objective is reliable completed work within finite included allowances, not the lowest API price. Harness efficiency can matter under a subscription. The size of that effect must be measured for the actual provider, plan, model and workload.

## Record separate resources

For each attempt, record task/variant ID, pinned repository snapshot, model and applied effort, harness/build, auth method, provider quota bucket and reset window, timestamps, success checks, retries, time and manual interventions. Record before/after provider counters with their actual measurement timestamps and precision. Keep account identifiers and snapshots private.

Use token counts, cached input and API-equivalent dollars only as diagnostic columns. They are not observed subscription consumption. Treat OpenAI coding allowance, Claude allowance and Pro web message caps as separate resources; do not add unrelated percentages. Do not infer that a shorter answer uses fewer message-limited Pro slots.

`reference/quota.py` rejects attribution across resets, changed buckets/units, nonfinite/decreasing counters, concurrent use, stale measurements and rounded observations. Exactness defaults to false. A missing measurement is unknown, not zero. A zero delta within a coarse or delayed counter is not evidence of free execution.

## Experiment design

Create representative backend, frontend, debugging, integration and bounded refactoring tasks with locked tests. Isolate worktrees and equivalent sandbox permissions. Compare both harness profiles at fixed model/effort before changing effort. Alternate order and repeat tasks without leaking one variant's fix into the other. Include failed, paused and retried attempts in total resource use.

Use a task-level paired analysis with uncertainty intervals; do not count repeated attempts as independent task samples. No fixed small sample proves rare-error safety. Choose the acceptable regression margin and practical savings target before running. Preserve required correctness, safety, recovery and privacy. Promote a route only after satisfying quality requirements, then compare resource/time trade-offs among passing routes.

For dynamic effort, compare fixed defaults with adaptive leases on the same task distribution. Measure CLM overhead and GPU contention, not just generated tokens. For Pro debates, measure total accepted-case cost in messages/time including clarification and rework. Do not optimize away necessary independent challenge.

## Runtime policy

Paid overflow, API-key execution and route switching after quota exhaustion are disabled unless the owner explicitly changes policy. Verify the effective auth/billing mode through each native product. Credential environment variables can change billing, so inspect configuration names and effective status without printing secrets. Do not remove authentication methods from a hosted Claude binary; simply decline to dispatch a job in a disallowed billing mode.

[Codex usage guidance](https://developers.openai.com/codex/pricing/) and [Claude Code accounting guidance](https://code.claude.com/docs/en/costs) inform the observers. Their current plan rules and observer precision must be revalidated locally. The repository contains no measured subscription savings yet.

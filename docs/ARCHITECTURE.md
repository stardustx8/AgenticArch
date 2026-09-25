# Architecture: one decision core, two harnesses

Version 2, 2026-09-25. The reference code is executable; host integration and real model evaluation remain local qualification work.

## Components and boundaries

The coordinator owns the task, scope, permissions, state transitions and evidence ledger. Its implementation can bind to custom Codex or Pi. Shared components are the model-routing catalog, hard policy, CLM adapter, verification rules, review protocol and private transactional state. Avoid two divergent products or a distributed agent platform.

CLM supplies contrastive judgments over a bounded context and declared candidate descriptions. A generation model implements code or conducts deep review. Deterministic tools establish observed compilation, test and change results. None of those roles implies authority for the others.

Use SQLite for local transactional task/case state and an outbox, ordinary Git for durable versioned artifacts, and filesystem-scoped worker processes. Persist before external submission; record an idempotency marker; reconcile uncertain sends before retrying. Never convert an unknown send into a second Pro conversation.

## Request path

Capture requirements, current working-tree snapshot, approved checks and exclusions. Identify architecture/research/consequential design before choosing a worker. Apply [policy floors](ROUTING-AND-VERIFICATION.md), then reject unavailable, unqualified, wrong-billing and exhausted routes. `reference/routing.py` compiles the surviving actions into compact CLM descriptions. Unknown subscription capacity is not zero cost, and high semantic similarity is not proof of competence.

Dispatch through the selected [Codex](../harnesses/codex/README.md) or [Pi](../harnesses/pi/README.md) profile. Keep only relevant tools/context active while retaining security, approvals, cancellation and provenance. Job envelopes bind task ID, session, snapshot, permitted paths, provider identity, effort, billing method and budget. Recheck the binding immediately before execution.

For fixed-model workers, the [effort gate](DYNAMIC-REASONING.md) may revise effort for a few upcoming generations. It cannot rewrite the overall task's risk classification, bypass Pro review or switch a running generation's model. Tool output enters history before the next decision.

After each substantive pass, inspect the real diff and run the approved checks on that exact snapshot. CLM may suggest a missing requirement test or next diagnostic, but cannot waive the evidence gate. Record failures, including pre-existing failures; resolve or explicitly disposition them rather than silently marking complete.

## Deep work

Pro authors the complete initial case solution. A selected Claude participant challenges it independently, then both improve it through the review repository. Their agreement applies to exact solution, requirement and evidence digests and the frozen participant binding. The original coordinator fetches the accepted commit, reconciles newly discovered local facts and implements. Material architecture/data/safety changes reopen the same case and Pro chat. See [the complete protocol](ESCALATION-PROTOCOL.md).

## State and failure recovery

Keep model sessions, case-to-chat bindings, bundles, worker tokens and machine paths private. Git stores sanitized requirements and design knowledge. On restart, reconstruct from durable records, invalidate effort leases, verify the observed remote head and resume only the original case/task binding. Duplicate outputs are deduplicated by case/turn/digest, not by their prose.

A missing local CLM falls back to deterministic routing/inspection, not a cloud classifier. Missing subscription access pauses that route, not a switch to API billing. A provider safeguard or fallback is not bypassed; record actual identity and pause acceptance when it differs from the required one. Debates and retries have finite per-run budgets that pause without fabricating agreement.

## Acceptance boundary

The kit's offline tests validate contracts and failure handling. They do not establish installed GPU behavior, provider billing, full host cancellation semantics, long-session cache retention or end-to-end autonomous implementation. Follow [the phased plan](IMPLEMENTATION-PLAN.md) and [the acceptance matrix](ACCEPTANCE-TESTS.md).

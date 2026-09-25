# State machine

## Local task

INTAKE -> RISK_ASSESSMENT -> ELIGIBILITY -> CONTEXT_READY -> WORKER_PENDING -> VERIFYING -> COMPLETE, RETRY or DEEP_REVIEW. Each transition has trusted input identity, scope and a durable event. Missing capability/auth/quota/context creates an explicit wait; it does not authorize a different billing method or waive checks.

A worker has a nested generation gate: NEED_DECISION -> PENDING_APPLICATION -> APPLIED -> IN_FLIGHT -> NEXT_CHECKPOINT. A still-valid lease can repeat the checkpoint without another CLM call. Only observed application permits IN_FLIGHT. New input, failure, model/manual/policy/scope/deployment change or resume invalidates the lease. Cancellation must settle before another generation starts.

## Deep case

PREPARED -> WAIT_MANUAL_TRANSFER or PRO_PENDING -> PRO_READY -> CLAUDE_PENDING -> PRO_REVIEW_PENDING -> continued reciprocal turns -> CONVERGED -> LOCAL_RECONCILIATION -> IMPLEMENTING -> VERIFIED -> CLOSED.

WAIT_PERMISSION, WAIT_CAPABILITY, WAIT_ENVIRONMENT, WAIT_HUMAN, PAUSED and CANCELLED are explicit states. A paused case records the exact next actor and reuses the same Pro chat. It is never labelled converged merely because a budget or tool stopped.

The case's selected Claude model is fixed within review_epoch. A deliberate participant change increments the epoch and removes current approval eligibility, but preserves previous immutable turns and all unresolved findings. Fresh challenge/response and matching approvals are required. Local material changes reopen a focused review round.

## Recovery

Persist intent before submission and receipt after actual readback. On restart verify task/case/session and current Git revision, reconcile uncertain sends, invalidate effort leases and resume only the matching operation. Do not use the most recent global chat/job. Keep one coordinator and serialized write windows. Historical receipts cannot approve new requirements, evidence, solution content or participant identity.

The schemas define records; reference code validates observations. Actual state persistence, locking and side effects remain host integration work, not proof supplied by a JSON state label.

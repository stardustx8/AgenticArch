# Runtime state machine

Normative target, not implemented by the pure reference kernel.

## Local task

```text
NEW -> INTAKE -> ROUTED -> WORKER_RUNNING -> VERIFYING
                            ^                  |
                            |-- RETRY ---------|
                            |-- ESCALATE ------| -> PRO_CASE
                                               | -> COMPLETION_REVIEW -> DELIVERED
                                               | -> WAIT_ENVIRONMENT / WAIT_CAPABILITY
```

The controller maintains an assessed task category and routing floor before dispatch. `assessment_only` cannot enter `WORKER_RUNNING` with write authority. `DELIVERED` requires successful final gates plus evidence of the requested delivery action. Stop/cancel can interrupt any active state; it does not erase side effects.

## Review case

```text
PREPARED -> PRO_PENDING -> PRO_READY -> FABLE_PENDING
                                       |        |
                      PRO_REVIEW_PENDING <------|
                            |                   |
                            |--- FABLE_PENDING -|
                            |
                      CONVERGENCE_CHECK
                            |
                         CONVERGED -> LOCAL_RECONCILIATION -> IMPLEMENTING
                                                               |
                                                          VERIFIED -> CLOSED
```

`CONVERGENCE_CHECK` is a local evaluation, not an extra model role. If it fails, the next actor addresses specific gaps; final approval-only turns may be needed after a content freeze. A `REVISE` or `BLOCKED` verdict does not converge. A new material local difference reopens `PRO_REVIEW_PENDING` in the same case/chat.

Every active state can pause as `WAIT_CAPABILITY`, `WAIT_ENVIRONMENT`, `WAIT_HUMAN` or `PAUSED`, storing a resumable prior state and next action. Invalid transitions are rejected. Budgets apply to actual completed turns/rounds, not UI polling. A six-round cap per run is a checkpoint boundary, not permission to implement an unapproved draft.

## Write-before-act and reconciliation

Before each external side effect, commit an outbox record locally: unique operation ID, case/turn, allowed destination, expected input hashes, state version, next action. Acquire the local lease. After the action verify the externally observed result and commit its receipt plus the state transition in one local transaction. A crash between side effect and receipt must reconcile externally before retrying.

For Git, validate branch parent and changed paths and use normal non-force updates. For browser messages, use an opaque turn marker and inspect the bound conversation. Neither an outbox nor a marker alone guarantees exactly-once delivery. Ambiguous observations pause instead of duplicating a submission.

## Persistent invariants

Task and case IDs are immutable. A bound Pro conversation cannot silently change. Counters are monotonic within an attempt series and their cumulative values survive resumes. Approval records reference immutable input/output content. Both actual participant identities and durable outputs must be validated before their verdicts count. Run state cannot be overwritten by instructions in repository content.

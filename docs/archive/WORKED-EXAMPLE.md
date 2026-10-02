# Worked example: accepted jobs must survive disconnection

This is an illustrative task, not a claim about a deployed product or a measured CLM result.

## Requirement and evidence

The owner asks for accepted jobs to remain retrievable after a client disconnects. Clarify the established contract from project evidence: does acceptance mean persisted, does a backend restart matter, and what idempotency/result-retention guarantees already exist? A new durability or delivery-semantics decision goes to the required Pro/Claude architecture workflow; a local classifier does not invent it.

Suppose the approved design requires durable acceptance, stable job IDs, resumable result retrieval and no duplicate side effects. The current implementation passes its ordinary connection tests.

## How the local decision layer helps

**Retrieve the right evidence.** Exact code search finds submission handlers and test names. The context relevance operator helps rank the persistence code, acceptance response, retry policy and result lookup contract. Requirements and approved invariants stay pinned even if a relevance score is low.

**Find the gap.** A per-requirement question compares durable-acceptance requirements with the actual observed tests. A passing reconnect test alone does not demonstrate backend-restart durability. `insufficient` requests investigation; it does not establish that the implementation is broken.

**Choose a discriminating observation.** The coordinator offers already-scoped diagnostic IDs: inspect the transaction boundary, replay a restart reproduction, inspect the persistence configuration. The model can suggest an ID; the executor verifies current permission, scope and prerequisites. It cannot generate and execute a shell command.

**Construct a real counterexample.** Within an explicitly authorized isolated environment, a test may accept a job, restart the service at a controlled point and retrieve the same job ID. Another may lose the response after persistence and retry with the same idempotency key. A local generator can propose input cases, but the approved contract supplies the oracle. A failure is observed only after execution.

**Improve the remote review.** If the result changes architecture, the new evidence enters the existing case. Claude and Pro receive the minimal reproducible failure, relevant transaction code and open objection. The disagreement classifier can link related findings but cannot mark the concern resolved. Pro continues the same chat, and both participants approve the updated exact solution version.

**Implement locally.** The original Codex or Pi coordinator checks the actual installed database/runtime and current worktree. Mechanical adaptations are recorded; changes to the agreed delivery semantics reopen review. Final tests are run against the final snapshot. The classifier never substitutes for those results.

## Why this is worth testing

The intended improvement is not merely a cheaper model call. It is fewer speculative repairs, fewer missing-context escalations and earlier discovery of untested guarantees. The comparison must measure accepted task outcomes, time, false alarms and missed defects against the same workflow without these operators.

## Offline illustration

From the repository root:

```sh
python3 tools/demo_decision_plane.py
```

This runs two **synthetic score fixtures** through the reference contract. It demonstrates `ABSTAIN` for insufficient evidence and `SHADOW` for an unqualified diagnostic recommendation. It performs no inference, project test, file mutation, browser action or Git push. The synthetic scores are not estimates of semantic accuracy.

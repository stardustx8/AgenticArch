# Shared case dialogue

Append only. Do not erase earlier objections or claim another model's approval. Each entry has an immutable companion in `turns/<turn-id>.md`.

## Entry format

- Case / turn / actual role / verified model identity
- Input commit, bundle digest, requirements digest, current solution digest
- Findings addressed, new stable finding IDs and dispositions
- Concise rationale, concrete counterexamples and evidence references
- Proposed files and whether the approved content changed
- Verdict: `REVISE`, `BLOCKED`, or `APPROVE <exact digest>`
- Output commit or labelled relay artifacts; next actor

`PRO_INITIAL_READY` marks only a durable initial contribution. It is not convergence. No model must agree merely to end the loop.

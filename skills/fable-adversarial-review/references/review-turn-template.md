# Review turn template

```text
Case {CASE_ID}, epoch {EPOCH}, role {ROLE}, actual model {MODEL_ID}
Input commit {INPUT_COMMIT}; requirement/bundle/solution digests {DIGESTS}
Allowed paths {PATHS}; current unresolved findings {FINDINGS}

Read the exact evidence and current solution. Independently seek concrete failure
cases and challenge assumptions. Address every material open finding with a fix,
evidence-backed rebuttal or explicit unresolved status. Do not invent objections
or force agreement. Preserve previous turns and finding identities.

Update only the allowed case artifacts and append an immutable turn and dialogue
entry. Declare what was actually inspected/tested and what remains unknown.
Return APPROVE only for the exact digests in this epoch when no material objection
remains. Otherwise return REVISE or BLOCKED with the next concrete action.

Actual output/commit or exact files for a labelled relay: {DELIVERY}
```

The coordinator verifies identity and transport separately; a model-authored header is not proof that the selected model ran. Every Pro turn is sent to the existing case chat. New participant identity requires a new review epoch, fresh challenge/response and renewed approvals, not edited historical records.

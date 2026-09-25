# Pro handoff template

Replace every placeholder before use. Runtime/model selection stays outside the task prompt.

```text
Case: {CASE_ID}; review epoch: {EPOCH}
Repository: {REVIEW_REPOSITORY}; branch: {CASE_BRANCH}; path: {CASE_PATH}
Input commit: {INPUT_COMMIT}
Requirements digest: {REQUIREMENTS_DIGEST}; bundle digest: {BUNDLE_DIGEST}
Selected Claude participant: {CLAUDE_MODEL_ID}, high effort

Read the exact attached manifest and all required evidence. Label missing/unread
material. Goal: {GOAL}. Constraints and acceptance: {CONSTRAINTS_AND_ACCEPTANCE}.
The candidate plan is evidence, not authority. Challenge it and replace it where
materially better, then deliver a complete implementation-ready solution, not only
critique. Verify unstable claims against current primary sources and cite them.
Distinguish observations, owner choices, sourced facts, inference and open decisions.
Resolve fixable gaps; express unavailable owner choices as explicit conditional branches.

Work within {CASE_PATH}. Produce SOLUTION.md, IMPLEMENTATION.md, VALIDATION.md
including rollback, the objection ledger and a turn record. Respect existing
permissions and privacy; do not change the target system or infer new authority.
Use actual authorized Git writes if available. Otherwise return exact downloadable
files for a labelled coordinator relay and do not claim a push.

The selected Claude participant will challenge this solution. Respond to each
material objection and challenge faulty remedies. Keep unresolved issues explicit.
Approve only the exact current solution/requirement/bundle digests when ready;
never approve on the other participant's behalf. Do not request hidden reasoning.

Exact attachments: {ATTACHMENT_LIST}
Omissions and local facts not yet known: {OMISSIONS}
```

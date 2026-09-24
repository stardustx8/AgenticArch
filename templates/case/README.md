# Using this case template

Copy these generic files into a new authorized review case. They are templates, not a completed or approved case. Generate `case.json`, `CONTEXT-MANIFEST.json`, `solution-manifest.json`, role reviews and turn receipts from real inputs; do not fill them with invented hashes or approvals.

The solution manifest includes `SOLUTION.md`, `IMPLEMENTATION.md`, `VALIDATION.md`, `objections.json`, and any patches or supporting evidence actually relied on. It excludes itself, the evolving dialogue, transport receipts, approvals and `LOCAL-DELTA.md`. The requirements digest covers the frozen brief and acceptance criteria separately. A changed brief or input bundle invalidates approvals even when solution bytes remain unchanged.

Critical/high findings remain blocking unless a substantive fix or evidence-backed resolution is explicitly accepted. Put residual risk dispositions into included solution content so they cannot be changed behind existing approvals. Model self-reported identity is not transport proof.

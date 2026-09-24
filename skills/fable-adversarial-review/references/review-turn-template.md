# Review-turn templates

Use real values and exact current revisions. Case paths are allowlisted, not arbitrary output paths.

## Fable challenge or follow-up

```text
Case {{CASE_ID}}, turn {{TURN_ID}}, actor Fable.
Work only in {{REVIEW_REPO}} / {{CASE_BRANCH}} / {{CASE_PATH}}.
Read exact input commit {{INPUT_COMMIT}}.
Bundle/requirements/solution digests: {{BUNDLE}} / {{REQUIREMENTS}} / {{SOLUTION}}.

Read raw requirements and evidence first; form an independent view, then assess
the current solution and DIALOGUE.md. Find concrete counterexamples, unsupported
claims, lost requirements, failures of correctness/security/recovery/concurrency,
or simpler materially better alternatives. Do not invent concerns. Evaluate
Pro's latest counterarguments as carefully as its initial proposal.

Co-produce a corrected complete result within the case scope. Track stable
finding IDs, severity, evidence, consequence, remedy and disposition. Append
DIALOGUE.md and write your immutable turn. Direct writes require actual tools
and authorization; otherwise return exact files for a labelled relay.

Give REVISE, BLOCKED, or explicit APPROVE for the exact frozen digests.
Any included file change needs a new digest and new approvals from both roles.
Do not approve on Pro's behalf. List unrun local validation and next actor.
```

## Pro continuation, always in the bound existing chat

```text
Continue case {{CASE_ID}}, turn {{TURN_ID}}, in this existing conversation.
Fable's committed turn is {{FABLE_TURN}} at {{INPUT_COMMIT}} in
{{REVIEW_REPO}} / {{CASE_BRANCH}} / {{CASE_PATH}}.
Read those exact files and current DIALOGUE.md; the relevant approved delta
attachments are {{ATTACHMENT_NAMES_OR_NONE}}.
Current bundle/requirements/solution digests: {{BUNDLE}} / {{REQUIREMENTS}} / {{SOLUTION}}.

Address each open material finding: fix it, rebut with evidence, or retain it
as an unresolved issue. Challenge flaws in the proposed remedies as well.
Update the complete solution, not only commentary. Preserve requirements and
scope. Cite current primary evidence for unstable material facts, and do not
claim local tests you did not run. Append your authored turn and return exact
artifacts/commit, addressed/open findings, digest-bound verdict and next actor.
You cannot approve on Fable's behalf. Do not force agreement to finish.
```

## Local return

Fetch the pinned case revision, validate manifests and both role approvals, then compare the target project's live state with the reviewed snapshot. Implement the approved intent in the original Codex task. Record local adaptations and their evidence. Reopen consequential deviations in the same case/chat; run actual acceptance checks before reporting completion.

# Case $case_id — brief

Local task `$task_id`. Written by the AgenticArch coordinator; the owner's words are
quoted verbatim below. Everything else is coordinator context and may be incomplete.

## Owner's task (verbatim)

<<<
$prompt
>>>

## Target

- Repository: `$target_slug`
- Base commit: `$base_commit` (also pushed as branch `$base_branch`). Work from this
  exact commit; the owner's uncommitted local changes are NOT included.
- Pro-relevant categories flagged by triage: $categories

## Triage summary (Codex, may be wrong)

$summary

Acceptance criteria (proposed):
$acceptance

Risks noticed:
$risks

## Start reading here (ranked by the local CLM)

$paths

## Required checks (run by the coordinator after implementation)

$checks

## Local history

Attempts before escalation:
$history

Last failure:
$last_failure

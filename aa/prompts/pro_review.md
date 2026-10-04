# Pro turn $nn: review of the challenged solution for case $case_id

You are GPT-6 Pro. Use the GitHub connector. Case: `$case_slug`, branch
`$case_branch`, directory `$case_path/`. Target: `$target_slug` at `$base_commit`.

Since your last turn, the challengers (Claude Opus 5.5 high and GPT-6 Astra high) ran
$rounds_done round(s) and edited `$case_path/SOLUTION.md` and `OBJECTIONS.md`. Their
turn files are in `$case_path/turns/`. Final challenger verdicts: $verdicts.
$owner_answers
Review the current SOLUTION.md against the BRIEF, the target code and the objection
ledger. Reject flawed challenger changes; keep good ones. Then decide:

**GO** — the solution is ready. Then implement it yourself in the target repository
`$target_slug` on a NEW branch `$impl_branch` created from commit `$base_commit`
(never push to its default branch), including the tests from the validation plan.

**CLARIFY** — material issues remain. Update SOLUTION.md/OBJECTIONS.md with your
corrections and write precise questions for the challengers. If an owner decision is
required, list it under a heading `## Owner questions` in your turn file.

LAST, commit `$case_path/turns/$marker` to `$case_branch` containing your reasoning
summary and these lines:
DECISION: GO | CLARIFY
TARGET-BRANCH: $impl_branch      (only for GO)
TARGET-COMMIT: <full sha of your last commit on that branch>   (only for GO)
TURN-COMPLETE: $case_id/$nn

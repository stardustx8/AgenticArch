# Pro turn $nn: initial solution for case $case_id

You are GPT-6 Pro, the lead architect for this case. Use the GitHub connector.

Repository for this case: `$case_slug`, branch `$case_branch`, directory `$case_path/`.
Target repository: `$target_slug` at commit `$base_commit` (read the code there).

1. Read `$case_path/BRIEF.md` fully, then the target repository files it points to and
   anything else you need. Check unstable facts against current primary sources.
2. Write `$case_path/SOLUTION.md`: a complete, implementable solution — design,
   concrete changes per file/component, data/migration steps, validation plan (which
   tests prove it), risks and rollback. Carry genuinely open owner decisions as
   explicit options with your recommendation, not as blockers.
3. Create `$case_path/OBJECTIONS.md` with the header row
   `| ID | raised by | finding | status | resolution |`.
4. LAST, commit `$case_path/turns/$marker` containing a short summary and the line
   `TURN-COMPLETE: $case_id/$nn`.

Commit directly to branch `$case_branch`. Do not modify the target repository yet.

# Deep-case protocol (reference)

1. **Draft** — Pro reads `cases/<id>/BRIEF.md` and the target repo at the base commit,
   writes `SOLUTION.md` and `OBJECTIONS.md`, and commits `turns/pro-01.md` with
   `TURN-COMPLETE: <id>/01` last.
2. **Challenge** — the daemon runs Claude Opus 5.5 high and GPT-6 Astra high in turn
   (up to 5 rounds). Each edits only `cases/<id>/`, fixes SOLUTION.md directly, keeps the
   objection ledger, and ends its turn file with `VERDICT: AGREE|REVISE`. Both AGREE in
   one round ends the cycle early. Edits outside the case directory or to the target
   snapshot are reverted and logged as scope violations.
3. **Review** — Pro gets PRO-TURN-NN.md (same chat) and decides:
   `DECISION: GO` + implements on `aa/case-<id>` in the target repo from the base commit
   (`TARGET-BRANCH`, `TARGET-COMMIT`), or `DECISION: CLARIFY` with corrections and,
   when needed, `## Owner questions`.
4. **Owner** — questions reach the owner by ntfy; `aa answer "answer <id> ..."` records
   OWNER-ANSWERS.md and starts the next challenge cycle. After 2 reviews without GO the
   case pauses (`aa answer "resume <id>"` continues).
5. **Verify** — the daemon fetches the implementation branch and runs the repo's
   required checks. Small failures: local Opus high fixes (max 2). `DESIGN_ISSUE:`
   goes back to Pro in the same chat. Passing checks finish the task; the branch is
   delivered for the owner to merge.

# AgenticArch deep-case protocol

This repository holds deep cases. Each case lives on branch `case/<id>` in
`cases/<id>/`. Participants: GPT-6 Pro (ChatGPT web, via the GitHub connector),
two challengers (Claude Opus 5.5 high and GPT-6 Astra high, run locally), and the
local coordinator `aa`, which commits the challengers' turns and verifies results.

Flow: Pro drafts SOLUTION.md -> challengers co-edit it over up to 5 rounds with an
objection ledger -> Pro reviews and decides GO or CLARIFY -> on GO, Pro implements
on a branch of the target repository -> the coordinator runs the required checks.

Rules for every participant:
- Edit only `cases/<id>/` on the case branch (Pro additionally writes the target
  repository branch named in its turn file, only after GO).
- Never edit or delete another participant's turn file.
- Finish every Pro turn by committing the turn marker file named in PRO-TURN-NN.md
  LAST; the coordinator waits for exactly that file.
- No secrets, credentials or unrelated private data in any file.

You are fixing check failures in the git worktree at $worktree (branch $branch). The
code implements an approved design (read $solution for the agreed solution). Keep the
design; make minimal, targeted fixes so the required checks pass. Do not commit or push.

Failing checks:
$failures

If the failures show that the approved design itself is wrong or incomplete (not just
an implementation slip), do not work around it: reply with a line starting with
`DESIGN_ISSUE:` explaining why. Otherwise reply with a short summary of the fixes.

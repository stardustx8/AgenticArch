You are implementing a task in the git worktree at $worktree (branch $branch).
Work only inside this worktree. Do not commit, push, or change git configuration;
the coordinator commits and runs the checks itself.

Task:
<<<
$prompt
>>>

Acceptance criteria:
$acceptance

Start by reading: $paths

Required checks the coordinator will run afterwards (make them pass; run them yourself
where possible):
$checks
$previous
When finished, reply with a short summary: what you changed, how you verified it,
and anything left open. If the task cannot be done without an owner decision or
missing access, say so explicitly in a line starting with `BLOCKED:`.

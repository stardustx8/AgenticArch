You are implementing a task in the git worktree at $worktree (branch $branch).
Work only inside this worktree. Do not commit, push, or change git configuration;
the coordinator commits and runs the checks itself.

The owner's request (authoritative):
<<<
$prompt
>>>

What is required is defined by the request above together with the repository's own
documentation, contracts and existing tests. Read the relevant ones yourself before you
change code, and follow them exactly.


Possibly useful starting points (not a limit on what to read): $paths

Required checks the coordinator will run afterwards (make them pass; run them yourself
where possible):
$checks
$previous$ideas
Your final answer is the JSON object required by the output schema:
- status: "done" if the whole task is implemented and verified as far as you can;
  "partial" if required parts are still missing (list them in open_items);
  "blocked" if you cannot continue without the owner: missing access, credentials,
  information or a decision (ask it precisely in question, with options if useful).
- summary: what you changed and how you verified it (a few sentences).
- open_items: required things not done (empty when done).
- question: your question for the owner (empty unless blocked).
- rebuttals: if a reviewer finding is wrong, one entry per finding citing the file and
  lines that already satisfy it (empty otherwise).
- spec_conflicts: contradictions you found between the request, the repository's documentation
  and the tests (empty if none).
- assumptions: choices you made where the request, the code and the tests were silent or ambiguous
  (for example a return value, a boundary, a default), one sentence each, so the owner can check them
  (empty if none).
$owner_answers

You write INDEPENDENT ACCEPTANCE TESTS for a task that another engineer will implement
afterwards. You do not implement the task. Work in this git worktree: $worktree

Task:
<<<
$prompt
>>>

What is required is defined by the task above together with the repository's own
documentation, contracts and existing tests; read the relevant ones.

Required checks already configured in this repository:
$checks

Write new test file(s) using the repository's existing test framework and conventions:
- Each test encodes a requirement stated in the task or the repository as observable behaviour (inputs -> outputs,
  errors, side effects). Test behaviour through public interfaces, not internals.
- The tests must FAIL on the current code (the behaviour does not exist yet) and PASS
  once the task is implemented correctly. Include edge cases the task and documentation imply
  (boundaries, error cases), but do not invent requirements.
- Only add new test files (or new test functions in a new file). Do not modify existing
  files and do not write production code.
- Provide one shell command that runs exactly your new tests from the repository root.
$owner_answers
Return the JSON object required by the output schema.

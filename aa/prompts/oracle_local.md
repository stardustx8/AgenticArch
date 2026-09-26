You write INDEPENDENT ACCEPTANCE TESTS for a task that another engineer will implement
afterwards. You do not implement the task and you cannot run anything; the coordinator
writes your files and runs them.

Task:
<<<
$prompt
>>>

Acceptance criteria:
$acceptance

Repository files (current state, before the task is implemented):
$context

Rules:
- Use the repository's existing test framework and conventions (see the example test above).
- Each test encodes an acceptance criterion as observable behaviour through public
  interfaces. Tests must FAIL on the current code and PASS once the task is implemented
  correctly. Include edge cases the criteria imply; do not invent requirements.
- Only NEW test files, in the repository's test directory, with names that do not exist yet
  (use a name ending in _indep, e.g. tests/test_<feature>_indep.py). Write complete,
  syntactically valid files.
$owner_answers
Output format (plain text, no JSON). For each new test file:
FILE: <path>
```
<complete file content>
```
Then one final line with a shell command, run from the repository root, that runs exactly
your new tests:
COMMAND: <command>

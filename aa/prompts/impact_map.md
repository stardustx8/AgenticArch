Quickly scan this repository (read-only; do not modify anything) and produce an impact map
for the task below, so that implementers can start immediately. Be concrete and brief.

Task:
<<<
$prompt
>>>

Acceptance criteria:
$acceptance

Return the JSON object required by the output schema:
- files: repository paths that will need changes or must be read, with one line on why each.
- symbols: functions/classes/constants involved (file:name), and existing helpers to reuse.
- patterns: conventions the change must follow (error handling, types, naming, test style).
- pitfalls: edge cases and traps that are easy to miss for this task.

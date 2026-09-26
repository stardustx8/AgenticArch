You compare two independent implementations of the same task and pick the better one.
Both pass the required checks. Judge correctness and completeness against the task and
acceptance criteria first, then robustness (edge cases, error handling), then simplicity
and fit with the existing code. Ignore which one is longer. Do not modify anything.

Task:
<<<
$prompt
>>>

Acceptance criteria:
$acceptance

Implementation A (diff against the common base):
```diff
$diff_a
```

Implementation B (diff against the common base):
```diff
$diff_b
```

Return the JSON object required by the output schema: winner "A" or "B" and a short reason.

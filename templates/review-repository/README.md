# GPT-Pro-Escalation

A dedicated workspace for versioned GPT-6 Pro/Fable review cases. Keep real cases private and subject to the approved external-data policy. This repository is separate from AgenticArch and from the software being implemented.

Use branch `case/<case-id>` and directory `cases/<case-id>/` for each case. One coordinator owns a case; only one participant writes at a time. Communicate through the case's append-only `DIALOGUE.md` plus immutable turn records. Approve exact solution content digests, not a moving branch tip.

Do not store credentials, browser profiles or private ChatGPT URLs here. Do not change another case, run target-project production operations, force-push, or change repository visibility. When Git tools are unavailable, the coordinator may commit exact model-authored files as a labelled relay.

A converged design is returned to the original local coding task for reconciliation, implementation and verification. It is not itself a finished software change.

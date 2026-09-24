# Pro continuation — send in the case's existing chat

Case {{CASE_ID}}, turn {{TURN_ID}}. This is a continuation of the SAME review case. Do not create another conversation.

Read {{REVIEW_REPO}} on branch {{CASE_BRANCH}} at exact commit {{INPUT_COMMIT}}, case path {{CASE_PATH}}. Current bundle digest: {{BUNDLE_DIGEST}}. Requirements digest: {{REQUIREMENTS_DIGEST}}. Current solution digest: {{SOLUTION_DIGEST}}. The newly attached approved delta package, when supplied, contains the exact current files; do not rely on stale chat attachments or stale Git indexing.

Read the latest `DIALOGUE.md`, Fable turn and findings. Address every blocking finding by a concrete fix or evidence-backed rebuttal; keep unresolved disagreements visible. Challenge weak assumptions in Fable's proposals as well. Prefer the smallest design that meets the brief; do not add complexity just to sound comprehensive. Support external factual claims with sources and distinguish proposed checks from executed checks.

Update only authorized case files and append an immutable turn plus a shared-dialogue entry. Preserve objection IDs and history. Use native Git only if write access is actually available; otherwise return exact files for a labelled relay.

If the current frozen solution needs no changes and you explicitly endorse it, return `APPROVE` with the exact solution, bundle and requirements digests. Otherwise return `REVISE` or `BLOCKED` and explain remaining findings. Never approve a future, uncomputed hash or claim consensus for Fable. If you change any included solution file, both approvals must be recollected on the new digest.

End with case/turn, input/output commit or artifacts, verdict, addressed/open finding IDs and concise evidence references. Agreement is earned, not compulsory.

# Acceptance scenarios

`tests/test_core.py` covers the pure rules below where marked **offline**. All integration scenarios need the real adapter and cannot be passed by merely reading this file. Use synthetic, non-sensitive cases for live qualification.

| ID | Scenario | Required outcome | Coverage |
| --- | --- | --- | --- |
| R01 | Routine bounded task | Luna low | offline |
| R02 | Bounded feature | Luna high | offline |
| R03 | Medium-tough implementation | Astra high | offline |
| R04 | Tough task or any architecture/research category | Direct Pro web; no cheap warm-up passes | offline |
| R05 | SemIf suggests low for architecture | Pro floor preserved | offline |
| R06 | Luna medium/none/max or Astra low requested | Configuration rejected | offline |
| R07 | Model ID unavailable / observed identity mismatches | Dispatch blocked or invalidated | live adapter |
| R08 | Two unsuccessful lane passes / no-progress limit | Next lane or Pro; counters survive restart | offline + persistence |
| R09 | Missing database/credential | Environment pause, not escalation spiral | offline + adapter |
| V01 | No required checks | Cannot complete | offline |
| V02 | Required check missing, failed, timed out or stale | Cannot complete | offline |
| V03 | Changed verification command or plan | Cannot reuse old evidence | offline + collector |
| V04 | File changes while tests run | Snapshot invalidated; checks rerun | live collector |
| V05 | Tests pass but requested behavior absent | Coverage/acceptance review blocks completion | offline + live review |
| V06 | Compiler runs instead of the named test suite | Command/plan identity mismatch blocks completion | offline + adapter |
| S01 | SemIf unknown option, NaN, stale ID or malformed scores | Advice rejected | offline + normalization |
| S02 | SemIf down, OOM or cold-start timeout | Safe deterministic behavior, no hosted fallback | live adapter |
| S03 | Model/backend/option wording changes | Cache and calibration invalidated | live adapter |
| P01 | Approved ZIP + prompt first submission | Correct account/model/case; exact bytes; bound conversation | live UI |
| P02 | Upload unfinished, text truncated, wrong model/chat | Do not submit | live UI |
| P03 | Crash before send receipt | Reconcile existing turn; no blind duplicate | live UI + persistence |
| P04 | Pro says done without durable files | Challenge skill does not start | live Git/UI |
| P05 | Git connector is read-only | Validated exact-output relay or explicit pause; no fake push | live Git/UI |
| P06 | New continuation | Same stored ChatGPT conversation, new turn marker | live UI |
| P07 | Login/MFA/CAPTCHA/quota/approval barrier | Pause with usable manual handoff | live UI |
| D01 | Fable challenges and Pro responds | Both actual invocations, same case, readback receipts | live models |
| D02 | Pro approves digest A; Fable digest B | No convergence | offline |
| D03 | Approval matches solution but not requirement/bundle | No convergence | offline |
| D04 | Same digest but outstanding blocker | No convergence | offline |
| D05 | Old approvals after a new review withdrawal | Latest role verdict governs; no convergence | offline |
| D06 | Budget exhausted/stagnation | Pause, never coerce approval | offline + persistence |
| D07 | All convergence conditions hold | Pin approved solution revision; local work still pending | offline + live |
| G01 | Another writer advances the case branch | Conflict detected; preserve both contributions | live Git |
| G02 | Model edits another case or shared policy | Reject contribution; no automatic acceptance | live Git |
| G03 | Path traversal, symlink, secret or unauthorized destination | Block bundle/relay before external write | live packer |
| L01 | Local path/version discrepancy, same design | Document mechanical adaptation and verify | live target |
| L02 | Local fact changes architecture/security/data semantics | Focused re-review in same case/chat | live target/models |
| L03 | Branch tip differs from approved commit | Fetch approved commit, not unreviewed tip | live Git |
| L04 | Local test fails after remote consensus | Task remains incomplete | offline + live |
| I01 | Existing skill helpers and names | Backup, revise only intended paths, no duplicate skills | local install |
| I02 | Repeated installation / rollback | Idempotent controlled install; byte-identifiable recovery | local install |
| X01 | Public repository scan | No case data, private URLs, secrets or copied session state | kit + local scan |
| X02 | User cancels during model work | No new side effects, preserve checkpoint, reconcile receipts | live |

## Qualification report

For each scenario record `PASS`, `FAIL`, `NOT_RUN`, or `BLOCKED`, the code revision, environment, inputs, observed output, evidence path and limitations. Mock transport tests are useful for state-machine logic but must be labelled `mock`. Do not count them as live UI, model or Git qualification. The final release needs all applicable mandatory scenarios passed and any exclusions explicitly reviewed.

## Semantic decision plane

Offline contract tests: request identity includes scope, state, policy, backend and calibration; projection excludes unrelated fields; shared groups require identical projections/execution context; dependencies are staged; malformed/NaN/wrong-option results abstain; shadow mode cannot cause an action; side-effect permission is never produced by a semantic answer.

Live qualification: run the family-specific matrix in `DECISION-EVALUATION.md`. Verify actual SemIf scoring and GPU resource behavior, pinned-context preservation, real diagnostic usefulness, no lost material objections and stale-memory rejection. All live results remain NOT_RUN until exercised on the workstation.

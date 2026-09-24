# Routing and verification policy

Normative configuration: `config/policy.json`. Human interpretation below must remain consistent with it.

## 1. Four lanes, with direct entry

| Lane | Model / effort | Typical work | Never use it to |
| --- | --- | --- | --- |
| `luna_low` | GPT-6 Luna / low | Spelling, narrow renames, small tests, mechanical changes | Make new design or security decisions |
| `luna_high` | GPT-6 Luna / high | Bounded features, isolated bugs, local logic with known contracts | Resolve architecture or research questions |
| `astra_high` | GPT-6 Astra / high | Medium-tough multi-file implementation, difficult bounded debugging | Replace the required Pro workflow |
| `pro_web` | GPT-6 Pro / web product mode | Tough problems, architecture, research, consequential design | Bypass the Fable challenge and local evidence gates |

Luna has an explicit two-value allowlist. Astra is high only in this policy. Pro is a distinct product workflow, not an API reasoning-effort string and not a synonym for Astra high. Fable is the independently invoked reviewer from the local challenge skill, not a fourth coding worker or a name the coordinator can impersonate.

Architecture-level work includes choosing service boundaries, state ownership, persistence models, security boundaries, data contracts, distributed coordination, or recovery semantics. Research includes selecting and assessing external evidence to answer an open design or technical question. These go directly to Pro, however short the requested output is. Mechanically reading local help to discover an installed command is capability discovery, not a substitute for substantive research.

Examples: a typo is Luna low; implementing a specified validator is Luna high; debugging a bounded concurrency defect may be Astra high; deciding the concurrency model, evaluating competing storage designs, or planning a destructive migration is Pro. A validated Pro design may later be divided into lower-lane implementation tasks without reopening settled decisions.

## 2. Routing precedence

Apply in order:

1. Respect an explicit owner stop, permission boundary, or unavailable required capability. Pause the affected action; never compensate by using an unauthorized transport.
2. A tough task or mandatory category (`architecture`, `research`, `security_design`, `migration_design`, `irreversible_change_design`) requires Pro.
3. An unassessed task receives an assessment-only route of at least Astra high. No implementation is permitted until the risk/scope assessment is complete; identified mandatory categories then go to Pro.
4. Use the deterministic complexity floor: routine -> Luna low; bounded -> Luna high; medium-tough -> Astra high; tough -> Pro.
5. A valid SemIf suggestion can raise that floor. It cannot lower it, waive a category, or authorize completion.
6. Keep escalation monotonic within a task attempt series. A validated decomposition or new accepted solution can create new child tasks with fresh floors; log that boundary rather than silently resetting attempt counts.

Missing model access returns `WAIT_CAPABILITY`. Do not fall back silently, manufacture a model ID, bypass quota limits, or purchase capacity. The adapter checks effective model/effort per dispatch; mismatches invalidate the pass as model-policy evidence.

## 3. Iterations and progress

One implementation pass ends when a worker hands back a diff or a no-change diagnosis and the controller captures verification. The counter is persisted once under a unique pass ID. Re-running a check is not another coding attempt. Retrying a browser transfer is not another model reasoning turn unless a new turn was actually submitted.

Initial defaults: two implementation passes per coding lane, six across the task's coding attempt series, and at most two consecutive passes without meaningful progress. These are engineering defaults to measure, not scientific optima. Meaningful progress is a resolved acceptance criterion, eliminated failure cause, or reduced failure set with evidence, not different wording in a model response.

For code-caused failures, retry within budget only when the next pass has a specific hypothesis. On exhausted lane budget or repeated non-progress, move to the next lane; Astra escalates to Pro. A hard category goes to Pro immediately. After six coding passes, obtain Pro review rather than spend more worker attempts. A revised and converged Pro solution can authorize a new bounded attempt series; retain the cumulative task history.

For missing dependencies, credentials, permissions, unavailable services, or unstable test infrastructure, use `WAIT_ENVIRONMENT` or `WAIT_CAPABILITY`; preserve the diff and diagnosis. Increasing model strength cannot manufacture an absent secret or a stopped database. Do not alter production infrastructure to make tests pass without separate authorization.

## 4. Verification contract

Before editing, identify checks from the repository's actual documented tooling and acceptance criteria. Freeze their IDs and definitions for the pass series. Commands use argument arrays, fixed working directories, bounded timeouts, controlled environment variables, and the normal sandbox. Untrusted model output cannot become a shell command.

For example, in an applicable Go project, tests use `go test ./...`; compilation uses `go build ./...`; analysis may use `go vet ./...`. Those are different checks. Discover the actual TypeScript, Python, or other project commands instead of inventing scripts that might not exist.

Every check record includes: check ID, command hash, plan hash, snapshot digest, tool/version, start/end time, exit code, status, timeout state, relevant log digest, and a bounded redacted diagnostic excerpt. Record missing tools and skipped checks explicitly. A zero exit code from the wrong command is not a passing required check.

Snapshot identity covers HEAD plus staged and unstaged modifications, relevant untracked inputs, executable bits where meaningful, lockfiles, and the verification-plan version. A plain HEAD SHA is insufficient for a dirty worktree. The production snapshot collector must protect against files changing during hashing or execution; a detected change invalidates evidence and triggers another snapshot and run. The reference content-digest helper is narrower and does not implement this collector.

Maintain a requirements-to-evidence map. Tests cover behavior; type checks and compilation cover their own properties; UI changes may require a real visual/interaction check. Include regressions or an explicit, reviewable justification that existing tests cover the change. SemIf may flag missing semantic coverage, but cannot fill it in.

## 5. Completion gate

All of the following must hold:

- The exact required check set is known and nonempty. Every required check ran and passed against the current snapshot and locked verification plan. No observed check has an unresolved failure/error/timeout.
- Every acceptance requirement maps to current evidence. The change is within the approved scope; regression coverage is added or justified; behavioral review is complete; there are no unresolved blocking findings.
- A Pro-required task has valid same-digest Pro/Fable convergence for the approved solution, plus a completed local reconciliation. Local adaptations do not invalidate its approvals.
- The final diff is inspected and the task's required delivery action is actually done. A local file is not a pushed commit; a pushed commit is not a deployment. Do not infer one from another.

There is no vacuous “all tests passed” with zero tests. A docs-only task still has a reviewed check plan, such as link/schema/content validation and a content acceptance review. Not-applicable checks are excluded from the required set with a recorded reason before completion; silently skipping them is prohibited.

A successful compiler or test suite establishes evidence, not the absence of all bugs. Completion means the defined acceptance contract is satisfied with disclosed limitations. It is not a guarantee of universal correctness.

## 6. Role of SemIf scores

Use selected options as suggestions after validation. Do not ship a universal rule such as “0.95 means safe to complete.” SemIf scores are conditional on option wording and the supplied option set. Calibration is workload-specific and can drift when model, backend, quantization, prompt, or task distribution changes.

Start in shadow mode. Route deterministic tasks without SemIf; use it at intake, ambiguous post-verification boundaries, and escalation questions. Cache only on a complete key: state digest, question/template version, ordered option descriptions, model and tokenizer revisions, backend/dtype/quantization, and calibration artifact. Cached decisions cannot survive a changed snapshot or question.

A malformed response, timeout, unknown option, nonfinite value, mismatched request ID, or unsupported schema becomes `UNAVAILABLE`, not an inferred answer. The deterministic fallback respects all mandatory floors and evidence gates. Autocompletion never depends solely on model confidence.

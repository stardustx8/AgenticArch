# CLM model and effort decisions

The authoritative maintained inputs are [the model catalog](../config/model-routing.json), [the evidence registry](../config/evidence-registry.json), [harness profiles](../config/harness-profiles.json) and the root policy. The [reference compiler and guards](../reference/routing.py) have offline tests; actual runtime dispatch and local qualification are separate.

## Three decisions, three authorities

The controller first establishes the task's minimum competence band, risk, permissions, exact model availability, current subscription path and quota. The four legacy `core.Lane` values are competence anchors, not an exclusive list of worker models. Medium-tough has Astra high and Opus medium/high peers. Tough work and mandatory design categories require the Pro anchor and a separate Claude reviewer. A lower worker route is never a substitute for missing Pro access.

CLM receives only eligible, qualified options as a typed choice. The JSON policy is not pasted verbatim into its state. The compiler renders a concise task description and self-contained candidate descriptions, with `insufficient`. Retain evidence and catalog hashes outside the learned decision. No score can enable an unavailable transport or authorize API billing. The precise prose-encoder contract is in [the adapter specification](CLM-ADAPTER.md).

The controller revalidates the same eligibility binding before dispatch. A changed snapshot, requirement, permission, model, quota or capability invalidates the advice. Shadow mode retains a verified baseline; advisory mode additionally requires trusted workload qualification bound to the exact decision context. `qualified_policy_digest` in the reference helper is an adapter-produced qualification receipt binding, not a string CLM may supply. If a baseline is unavailable, the owner or an already-approved deterministic fallback policy may select another qualified peer; do not silently activate an unqualified one.

## Model fit and evidence

Model descriptions are conservative task-fit priors, not numerical estimates of success. No permanent rule says backend equals Pro or frontend equals Opus. Pro is required by complexity/design purpose; medium implementation choices are evaluated on task families. Sources retain exact versions, benchmark populations, harnesses, efforts, multiple-attempt costs and editorial limitations. Future Fable5.5 is pending with no active route. See [the research](MODEL-AND-HARNESS-RESEARCH.md).

The model catalog stores only small effort menus: Luna low/high, Astra high, Opus medium/high, Fable5.1 high. Pro's effort is null because this is a required web product, not a local API effort parameter. Opus review uses high. Baseline settings are starting choices to measure, not a claim of global optimality.

## Dynamic effort and leases

Use `compile_effort` only at an authorized pre-generation boundary. The controller supplies the minimum for this specific approved step. A mechanical step within a bounded plan can permit Luna low, but only after its scope is actually reduced; reading a file does not establish low reasoning need. A substantive review retains high. A single remaining effort bypasses CLM entirely.

The lease question is a second conditional decision from the catalog, asked only after the selected effort is valid. It chooses 1, 2, 5 or 10 generations. Do not evaluate a lease against hypothetical future tool outputs. `insufficient` means reassess after one generation while preserving the current verified allowed effort. Active leases avoid unnecessary CLM calls.

Before sampling, the harness adapter must confirm effective model, effective effort and generation. `accept_effort` rejects clamping or a missing receipt. A lease never changes a model. The adapter increments its boundary revision after accepted user input, tool failure, manual override, compaction, model/policy/capability changes, cancellation or reset. The lease is bound to session, model, revision and generation interval. Check the exact settings on every retained generation; a prior receipt does not authenticate a later changed worker.

The native Codex and Pi integration points differ; follow their [Codex](harnesses/CODEX.md) and [Pi](harnesses/PI.md) profiles. Provider-specific cache reuse and hidden reasoning state are not interchangeable. Fail closed on missing hooks or use an explicitly verified fixed effort, not an invented APPLIED event.

## Quota and learning

Quota arithmetic is deterministic. The helper returns null for missing counters, reset/mismatched windows, concurrent unrelated consumption or invalid values. Production collection must additionally record observation time, dashboard precision and causally isolated windows. Never impute zero from missing data. Workload selection considers quality, rework and elapsed time alongside allowance use. API-equivalent dollars stay separate. See [the evaluation protocol](QUOTA-EVALUATION.md).

Fine-tuning the CLM head on actual route outcomes comes after a reliable dataset exists. Preserve negatives, abstentions, project/time holdouts and exact candidate text versions. Do not train a predictor to reproduce its own unverified answers. Changing a head, renderer, candidate description or effort menu requires requalification and invalidates cached decisions.

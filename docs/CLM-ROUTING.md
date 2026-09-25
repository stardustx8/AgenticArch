# CLM model and effort decisions

This document preserves the concurrently published v1 compiler contract. Its maintained fixture is now [the v1 compatibility catalog](../config/compat/model-routing-v1.json), with [descriptive evidence IDs](../config/evidence-registry.json) and [high-level harness profiles](../config/harness-profiles.json). Its implementation remains unchanged in [routing_compat.py](../reference/routing_compat.py), exported through the original `reference.routing` import path.

New integrations use the active [v2 catalog](../config/model-routing.json), [v2 routing contract](ROUTING-AND-VERIFICATION.md) and [joint effort/lease decision](DYNAMIC-REASONING.md). The v1 compiler is retained for compatibility and regression evidence, not a second independently active production policy. The four quality tiers now contain six explicit `core.Lane` model/effort values. The code versions have different envelope names and generation indexing; never mix their leases or silently translate their capability records.

## Three decisions, three authorities

The controller first establishes task complexity, risk, permissions, exact model availability, current subscription path and quota. Medium-tough has Astra high and Opus medium/high peers. Tough work and mandatory design categories require the Pro anchor and a separate Claude reviewer. A lower worker route is never a substitute for missing Pro access.

The v1 compiler gives CLM only eligible options as typed choices. JSON policy is not pasted verbatim into state. Each candidate has a self-contained description and the `insufficient` option. The controller retains evidence/catalog hashes and refreshes the same eligibility binding before dispatch. A changed snapshot, permission, model or quota invalidates advice. Shadow mode retains a verified baseline; advisory mode additionally requires an adapter-produced qualification binding. CLM cannot supply that authorization.

## Model fit and evidence

Descriptions are conservative task priors, not numerical success estimates. Backend does not always mean Pro; frontend does not always mean Opus. Pro is required by design complexity, while implementation peers need task-family evaluation. Preserve source versions, efforts, benchmark populations and editorial limits. Future Fable 5.5 remains pending with no active route. See [the concurrent research](MODEL-AND-HARNESS-RESEARCH.md) and [the current evidence interpretation](MODEL-EVIDENCE.md).

## Retained v1 effort contract

`compile_effort` runs only at a permitted generation boundary with an explicit next-step minimum. A singleton menu bypasses CLM. Its legacy catalog describes a separate conditional lease question, evaluated only after the effort is valid; never speculate on future tool output. Leases count 1, 2, 5 or 10 generations, starting at generation 1. `accept_effort` requires a matching model/effort/generation acknowledgment and rejects clamps or missing receipts. Manual overrides and changed boundary revisions invalidate the lease.

The active v2 `EffortGate` starts its generation index at zero and chooses joint effort/lease actions. It adds explicit pending-application and in-flight lifecycle enforcement. Do not use one version's receipt with the other's state. Both profiles must prove native application, cancellation and provider mapping rather than infer them from setter existence. Cache and private reasoning state remain provider-specific.

## Quota and learning

The retained `quota_delta` rejects mismatched pools/windows, concurrent use and invalid values, but its caller must additionally verify measurement precision and timestamps. The current strict [quota contract](SUBSCRIPTION-EVALUATION.md) implements those checks separately. Missing observations are not zero. API-dollar estimates are not subscription usage.

Fine-tune only after a reliable outcome dataset exists. Preserve failures, abstentions, task/project/time holdouts and exact candidate text. A changed head, renderer, candidate or effort menu invalidates previous qualification. The compatibility layer does not waive these conditions.

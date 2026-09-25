# Validation report

Date: 2026-09-25. Preparation environment: Linux, Python 3.13.5, Node 22.16.0 and TypeScript 5.8.3. This is validation of the implementation kit, not the owner's live workstation.

## Executed

| Check | Result | Scope |
| --- | --- | --- |
| `python3 -m unittest discover -s tests -v` | 189 tests passed | Original policy, evidence, convergence, installer and decision-plane checks, plus peer routing, exact model/effort restrictions, subscription eligibility, CLM wire validation, token bounds, effort acknowledgments, quota attribution and reviewer epochs; preserves 13 concurrent CLM adapter tests and 25 routing/compiler tests (only the latter fixture path changed) |
| `python3 tools/check_kit.py` | Passed | JSON syntax, six policy lanes/eight routes, evidence references, nine operators, CLM fixture, both harness profiles, portable skill consistency and local links |
| `python3 tools/demo_decision_plane.py` | Passed | Synthetic decisions; no model inference or action |
| `python3 tools/preview_routing.py --harness codex` and `--harness pi` | Passed | Synthetic subscription bindings render the expected candidate requests; no live tokenizer or provider call |
| `tsc --strict --target ES2022 --module commonjs` and Pi structural fixture | Passed | TypeScript adapter compilation, applied settings, stale bindings, clamping and post-await re-observation |
| JSON Schema meta-validation and routing-catalog validation | Passed | All schema documents are valid Draft 2020-12 schemas; the routing catalog satisfies its schema. Semantic owner-policy constraints are tested separately in Python |

The optional JSON Schema check used the installed `jsonschema` library. The dependency-free kit command does not require that library or claim complete schema enforcement.

Reproduce the Pi fixture without installing Pi:

```sh
tmp=$(mktemp -d)
tsc --strict --target ES2022 --module commonjs --outDir "$tmp" harnesses/pi/effort-adapter.ts
node harnesses/pi/test-effort.cjs "$tmp/effort-adapter.js"
```

## Not executed

Actual CLM inference, tokenizer/deployment attestation, calibration, native Codex checkpoint integration, live Pi hooks, subscription authentication or accounting, target-project tests, GPU memory measurements, skill installation and genuine Pro/Claude review remain **NOT_RUN**. No independent model review of this revision has been performed. No quota savings percentage or model-routing accuracy has been measured.

The HTTP client and native-boundary adapters are real integration components, but the caller must provide trusted deployment observations, native locking/abort guarantees and qualified runtime bindings. A passing fixture cannot establish those properties on an uninspected host. Python 3.11 is the intended minimum; only Python 3.13.5 was exercised here.

All semantic operators and routing remain in **shadow** mode. Automatic Pro web operation is unqualified; the case-preserving manual route remains the default. The separate operational review repository is not provisioned by this change.

## Publication verification

Publish as a normal child of the current remote `main`. Verify GitHub's resulting source-tree SHA against the staged local tree and read back the branch head and representative files. Publication is established by those receipts, not by this report, a local commit or an archive. See [publication guidance](PUBLISHING.md).

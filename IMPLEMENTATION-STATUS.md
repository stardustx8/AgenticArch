# Implementation status

2026-09-25, kit revision 2.

## Implemented and offline-testable

Shared v2 policy and model/evidence registry; CLM request rendering and real loopback-only HTTP client; strict typed response/deployment/token-limit validation; subscription-only route eligibility and Astra/Opus peer tiers; joint effort/lease option generation; generation acknowledgment/state invalidation; quota attribution; participant-bound review epochs and original completion/evidence safeguards.

Both harness packages are present on main. Codex includes a native-checkpoint host contract; Pi includes a TypeScript setter/readback/abort adapter and structural fixture. The two actual skills are revised with self-contained references and the existing dry-run, backup-preserving installer. Requirements, architecture, evidence limits and cross-session handoff are current.

The concurrently published generic-choice CLM API and its 13 tests are preserved through compatibility exports. The concurrent v1 routing compiler/catalog and its 25 assertions-preserving tests are retained through an explicit versioned compatibility boundary. The integrated Python suite passes 189 tests. See the revision ledger for the explicit merge and requirement-ID mapping.

## Not implemented or not locally qualified

The complete persistent coordinator/outbox supervisor, actual native Codex patch integration, full Pi extension wiring, installed CLM encoder/head/tokenizer, live subscription/billing observers, native Pi provider authorization, target-project execution, skill installation and real Pro/Claude case exchange remain local implementation/qualification work. No independent two-model review of this kit has been performed.

Automatic Pro web operation remains unqualified; manual transfer is the default. The operational review repository has not been provisioned here. Fable 5.5 is pending, with no active route. No actual subscription saving or optimal local effort frontier has been measured.

## Verification and publication

Read [the validation report](docs/VALIDATION-REPORT.md). Passing tests establish fixture/contract behavior only. Verify the actual remote main revision and full source tree when publishing; source availability does not imply runtime installation. New sessions start with START-HERE and SESSION-HANDOFF.

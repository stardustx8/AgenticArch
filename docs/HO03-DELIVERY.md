# HO-03 delivery status

27 September 2026. This branch contains the three upper-edge project builders and the integrated six-project catalog in `tools/ho03_projects.py`. They supply twelve validated stage contracts, not measured native-worker difficulty. The remaining tested integration is supplied in the HO-03 file and git-format-patch handoff because the worker-file write was blocked. It is not represented as already on this branch. Do not start the new native comparison from the partial branch alone.

## Upper-edge projects

`u03_jobs`: durable tenant-scoped idempotent requests, lease expiry and fencing, then transactional outbox continuity, cancellation, migration and a reconnecting JavaScript reducer.

`u03_temporal`: knowledge-time/revision/event-time selection without resurrecting voided records, then temporal joins, exact per-row monetary rounding and atomic cross-table replay.

`u03_restore`: read-only safe planning and digest checks, then a durable journal, rollback at precommit failure points, external-edit conflict preservation and idempotent recovery.

The catalog adds middle probes for source-grounded transcript claims and atomic incremental imports, plus an explicitly previously exposed policy bridge. All are synthetic. Local database/filesystem/reducer execution is real; native model calibration, remote-machine behavior, power-loss recovery and browser UX are not established by these fixtures.

## Integrated handoff

The supplied integration fixes unresolved-tier handling, stage-local protection attribution, persistent resume deadlines and hook-tamper auditing. It adds a fixed Astra-high minimal comparison against full race/gates, separately scored local awaiting-response escalation packages, source/configuration-pinned plans and mandatory operator calibration checks. Native memory controls use the existing subscription CLI configuration without credential relocation or permission changes. Actual installed-CLI behavior and log isolation require the operator preflight.

Calibration pauses after 2, 6 and 12 trajectories. Its middle-band rule requires pooled stage correctness in [0.2,0.8] and at least one mixed project. Evidence defects, critical findings or protected-file loss stop regardless of a contradictory audit. An upper-only alternative may replace the still-unrun upper portion after a clean middle-band discrimination stop; it cannot bypass that stop to unlock extension.

The integrated plan budgets 24 calibration stages, 84 extension stages and six separately scored routing stages. Middle/upper trajectories have 600/1200-second limits. Round caps are four/twelve/1.25 hours, with a three-hour, twelve-stage alternative upper diagnostic. These are caps, not promised durations or quota measurements. Whole-cgroup limits and private log audits remain mandatory.

Production defaults and completion authority remain unchanged. `docs/SESSION-HANDOFF.md` is not edited. The private research report and final response carry exact source, patch and validation hashes, application instructions and open risks. No production gain, reliable difficulty boundary, installed-provider compatibility or independent model review is claimed from local mechanics alone.

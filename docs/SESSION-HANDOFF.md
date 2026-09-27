# Session handoff

Updated 2026-09-26 late (Claude Code session on the workstation, branch `m1-working-runtime`).

## State

The `aa` runtime is installed and running on the workstation (see
[IMPLEMENTATION-STATUS](../IMPLEMENTATION-STATUS.md) for what was verified live). Owner
decisions are in [OWNER-REQUIREMENTS](OWNER-REQUIREMENTS.md) (O01-O19) and DECISIONS
D011-D022. PR #2 (`m1-working-runtime`) is open for the owner.

Added 2026-09-26: Gemma 4 31B (vLLM FP8, `aa-gemma`) as neutral judge and extra oracle
author (D021); oracle tests, mutation gate, best-of-2 race (D020); idea flags; the harness lab
(`tools/lab.py`, tasks in `eval/lab/tasks/`); fixes found by the lab (oracle disputes, owner
question cap, model-call cap, hang-safe grading); daemon memory cap (48G, OOMPolicy=continue);
deep-case reading list by BM25 (D022). GPU ECC is enabled (no capacity loss).

## Harness optimisation with GPT Pro (HO-01)

- Private branch `research/harness-opt-01` of stardustx8/Dashboard (local clone
  `~/dev/GPT-Pro-Escalation`): BRIEF.md, inputs, owner answers and work profile, Pro's
  REPORT/SCORING/EXPERIMENTS, reviews, results, turn files (`turns/PRO-TURN-NN.md`).
- Pro's code: AgenticArch PR #3 (`pro/harness-opt-01`), draft, all new policies off by default.
  Lab rounds run from a pinned detached worktree (currently
  `~/dev/GPT-Pro-Escalation/.ho02-local/code`, never the main checkout); local round output in
  `~/dev/GPT-Pro-Escalation/.ho02-local/`, round-1 records in `~/ho01-runs-20260926/`.
- After starting any long round, check the first ~15-25% of results for validity (ceiling,
  artefacts, leakage) before letting it run on (owner, 2026-09-27).
- Round 1 (`ho01-r1b`, 120 runs): minimal 80% in 1.1 min, full 77% in 2.7 min; full
  regresses `b1_statement_amounts` (drops existing input rejection) 4/5 times. With the owner's
  trade-off (O18: 2 pp less correct is fine for 2x faster) the minimal pipeline is currently the
  better deal on these tasks; the task suite does not yet represent the owner's work (O19).
- Project round 2 (`ho02-project-r2`) was stopped after 18/60 trajectories: most projects at
  ceiling, and a Pro-escalation artefact (no GitHub origin in the lab). Pro turn 03 redesigns. When it ends: review the diff with a fresh subagent, run EXPERIMENTS.md rounds from
  the worktree under `systemd-run --user -p MemoryMax=48G -p OOMPolicy=continue`, push results
  to `results/<round>/`, write `turns/PRO-TURN-NN.md`, give the owner the one-line prompt.

## Next steps

1. Continue HO-01 as above; then decide defaults (possibly minimal pipeline + proven gates).
2. First real deep case against a GitHub target repo (owner pastes the Pro prompts).
3. Install skills on the Mac (`tools/install_skills.py`).
4. Optional owner actions: `sudo efibootmgr -o 0002,0000` (boot Linux by default; firmware
   currently boots Windows first), `sudo loginctl enable-linger rosh` (units without login),
   `sudo apt install ipmitool` (fan readings via the BMC).

## Sandbox

`~/dev/aa-sandbox` is a local test repo used for the live smoke tests.

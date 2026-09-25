# Owner requirements

Version 3.0, 2026-09-25 (owner Q&A). Supersedes v2 where they conflict; v2 is in Git history.

## Goal

A daily working tool soon, not a specification kit. Few Pro cases (estimated up to 10-20
a day); manual one-line Pro prompts are acceptable.

## Requirements

| ID | Requirement | Where |
| --- | --- | --- |
| O01 | Coordinator runs as a background daemon on the Linux workstation; the Codex desktop app is the front end (skill), plus `aa` CLI. | aa/daemon.py, skills/agenticarch |
| O02 | Tasks are triaged by the Codex model and CLM; on disagreement the owner decides (ntfy). The tier is authoritative for the worker. | aa/tasks.py |
| O03 | Luna low (routine), Luna high (bounded), Astra high or Opus 5.5 medium/high (medium-tough), Pro deep case (tough/architecture/research/security/migration/irreversible design). | aa/workers.py, aa/tasks.py |
| O04 | CLM (Contrastive-LM, local, loopback) steers from day one: tier vote, peer choice, context selection; effort once per-generation switching exists. | aa/clm.py |
| O05 | Deep case: Pro drafts -> Opus 5.5 high and Astra high challenge and co-edit ~5 rounds -> Pro reviews GO/CLARIFY; after 2 reviews without GO pause and ask the owner. | aa/cases.py |
| O06 | Fable 5.1 dropped; Fable 5.5 replaces Opus as challenger after release and qualification. No gpt-6-sol/terra routes. | config deep.challengers |
| O07 | Pro uses the ChatGPT GitHub connector (write verified by owner): reads the case branch, writes its turns, and after GO implements on a target-repo branch. No evidence ZIP. | aa/prompts/pro_*.md |
| O08 | Owner is notified by self-hosted ntfy (Tailscale) with the one-line prompt and reply buttons. | aa/notify.py |
| O09 | Cases live in the new private repo stardustx8/GPT-Pro-Escalation; AgenticArch stays public and case-free. | config case_repo |
| O10 | After GO, local test failures are fixed by Opus high; design problems go back to Pro. | aa/cases.py |
| O11 | No cross-model code-review loop for normal tasks. | aa/tasks.py |
| O12 | Required checks: per-repo `.agenticarch.toml`, else autodetect confirmed once by the owner. | aa/checks.py |
| O13 | Remote execution subscription-only (ChatGPT Pro, Claude Max); never API credits or paid overflow. | aa/workers.py |
| O14 | Per-generation effort switching via a Codex fork used only for headless workers; desktop app unchanged. | not yet implemented |
| O15 | Skills installed on the workstation and the Mac. | skills/, tools/install_skills.py |
| O16 | Git: branch + PR per milestone; SSH auth. Moderate cleanup: compat layers removed, Pi parked, docs trimmed. | this revision |

## Environment (verified 2026-09-25)

Linux workstation, RTX PRO 6000 Blackwell 96 GB, ~122 GB RAM, Codex CLI 0.155.1 (ChatGPT
login) plus the Codex desktop app, Claude Code CLI 2.1.282 (Claude Max login), rootless
Docker, Tailscale to the owner's iPhone. Local AI Lab models (artemis, ortenzya) share the GPU.

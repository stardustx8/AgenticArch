# AgenticArch

A working coding coordinator for one workstation: tasks are triaged by Codex and a local
semantic decider (SemIf), executed by subscription workers (GPT-6 Luna/Astra via Codex,
Claude Opus 5.5 via Claude Code), verified by the coordinator's own check runs, and tough
problems go to GPT-6 Pro in ChatGPT web with Opus x Astra adversarial challenge rounds.

```sh
aa task --repo ~/dev/myproject "Add a --json flag to the report command"
aa status
aa doctor
```

## Start here

- [RUNTIME](docs/RUNTIME.md) — how it runs, flows, operations, known limits
- [ARCHITECTURE](docs/ARCHITECTURE.md) — shape, roles, invariants, code map
- [OWNER-REQUIREMENTS](docs/OWNER-REQUIREMENTS.md) — what the owner decided
- [SESSION-HANDOFF](docs/SESSION-HANDOFF.md) — current state and next steps
- [Skills](skills/README.md) — `agenticarch`, `prepare-sol-pro-architecture-review`, `fable-adversarial-review`

| Work | Worker |
| --- | --- |
| Routine | GPT-6 Luna low |
| Bounded | GPT-6 Luna high |
| Medium-tough | GPT-6 Astra high or Claude Opus 5.5 medium/high |
| Tough, architecture, research | GPT-6 Pro web drafts -> Opus 5.5 high x Astra high challenge -> Pro GO + implements |

Remote execution is subscription-only (no API keys, no paid overflow). Deep cases live
in the private repo `stardustx8/GPT-Pro-Escalation`; nothing private goes in this repo.

## Install (workstation)

```sh
ln -sf $PWD/bin/aa ~/.local/bin/aa
cp config/aa.example.toml ~/.config/agenticarch/aa.toml
for u in deploy/systemd/*.service; do ln -sf $PWD/$u ~/.config/systemd/user/; done
systemctl --user daemon-reload
systemctl --user enable --now aa-ntfy-forward aa-semif aa-daemon
aa doctor
```

Prerequisites (see RUNTIME): Codex CLI with ChatGPT login, Claude Code CLI with Claude
Max login, the SemIf container image `ai-lab/private-semif` with Qwen3.5-4B in
`~/.local/share/agenticarch/semif/`, ntfy in Docker, SSH access to GitHub.

Decider benchmark: `python3 tools/eval_decisions.py --backends semif,rules` (see
[eval/RESULTS.md](eval/RESULTS.md)).

## Tests

```sh
python3 -m unittest discover -s tests
python3 tools/check_kit.py
```

`tests/test_aa_runtime.py` drives the full task and deep-case state machines with fake
model workers against real temporary git repositories and bare remotes.

`reference/` contains the earlier contract validators; `parked/pi` the parked Pi
harness package; `docs/archive` the superseded pre-runtime design documents.

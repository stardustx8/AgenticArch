# Skills

| Skill | Purpose |
| --- | --- |
| [agenticarch](agenticarch/SKILL.md) | Queue/inspect/answer coordinator tasks (`aa`). |
| [prepare-sol-pro-architecture-review](prepare-sol-pro-architecture-review/SKILL.md) | Start a GPT-6 Pro deep case (legacy identifier). |
| [fable-adversarial-review](fable-adversarial-review/SKILL.md) | Opus x Astra challenge rounds of a deep case (legacy identifier). |

Install on the workstation and the Mac with `tools/install_skills.py` (dry run by
default, backups before `--apply`):

```sh
python3 tools/install_skills.py --target-root ~/.codex/skills
python3 tools/install_skills.py --target-root ~/.codex/skills --backup-root ~/.local/share/agenticarch/skill-backups --apply
```

On the Mac the skills call `aa` over Tailscale SSH (`ssh rosh@rs-workstation-linux aa ...`).

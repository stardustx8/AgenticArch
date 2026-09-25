# Revised local skills

These are directly revised skill definitions with complete local references:

- [prepare-sol-pro-architecture-review](prepare-sol-pro-architecture-review/SKILL.md): evidence packaging and GPT-6 Pro web handoff, followed automatically by the challenge skill.
- [fable-adversarial-review](fable-adversarial-review/SKILL.md): reciprocal Pro/selected-Claude co-production in the review repository, then original Codex or Pi implementation.

The exact identifiers remain stable. Do not install additional same-named copies into several discovery roots. The definitions no longer select the legacy reviewer defaults. They do not claim that writing Markdown grants model, repository, browser or tool capabilities.

## Installation

First locate the existing skills in the **actual selected harness configuration** and inspect any auxiliary helpers. The owner supplied the two main definitions; unrelated local scripts were not available to this kit. Preserve them. The new `references/` documents are self-contained and are part of the revision, not reconstructions of unseen prior files.

`tools/install_skills.py` performs a dry run unless `--apply` is supplied. Supply the discovered existing skill root, not a guessed one. For an applied update it backs up the original skill trees and records file hashes; the backup root must be outside both source and installed skill discovery trees. It updates only files shipped in these two skill folders, preserving other helper files. Stop on symlinks or special files rather than following them.

```sh
python3 tools/install_skills.py --target-root /verified/skill/root
python3 tools/install_skills.py --target-root /verified/skill/root \
  --backup-root /private/skill-backups --apply
```

Restart/reload only as required by the actual client. Confirm each identifier resolves once; forward-test a synthetic manual case before enabling any broader integration. See [the implementation plan](../docs/IMPLEMENTATION-PLAN.md) for live qualification and rollback. Automated Pro web transfer remains gated by [current platform restrictions](../docs/COMPUTER-USE-GATE.md).

Fable 5.1 and Opus 5.5 are selectable actual Claude participants; the skill name remains unchanged. Subscription and case-epoch checks apply in both harnesses. Future Fable 5.5 is not installed or activated by this package.

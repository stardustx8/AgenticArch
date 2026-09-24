# Publish the implementation kit

Target: `https://github.com/stardustx8/AgenticArch.git`, branch `main`.

## Work from the published repository

For future development, clone or fetch the actual remote repository and read `START-HERE.md` plus `docs/SESSION-HANDOFF.md`. The original local bundle/ZIP is a historical transfer copy, not the latest shared state. Do not push its unrelated preparation history over an existing remote branch. Preserve concurrent work, use normal integration commits and update the handoff alongside source changes.

## Publication prerequisites

Use a GitHub identity already authorized by the owner. Ensure the installed GitHub app actually includes AgenticArch in its repository selection and can write repository contents. User-level `push: true` metadata is not proof that the connected app can write. A rejected write must be reported, not worked around with another account or altered permissions.

Use current readback to distinguish a truly empty repository from an existing branch. Do not force-push, discard files, change visibility or bypass branch protection. Publication permission for this kit does not automatically create the separate review repository or export real case data.

## From the companion Git bundle

The bundle contains this kit's initialized local `main`, with no runtime case data or credentials. In a new destination directory:

```sh
git clone --branch main /absolute/path/AgenticArch.bundle AgenticArch
cd AgenticArch
python3 -m unittest discover -s tests -v
python3 tools/check_kit.py
git remote set-url origin https://github.com/stardustx8/AgenticArch.git
git ls-remote --heads origin
git push -u origin main
```

The normal push safely rejects non-fast-forward remote changes; never add a force flag. If the remote is no longer empty, fetch it and reconcile its contents in a reviewed worktree before publishing. The bundle is a transport convenience, not proof that GitHub received anything.

## From the source ZIP

Extract into a new directory, inspect the kit and run the checks above. The archive contains source files, not `.git`. In that extracted kit directory, initialize `main`, add only the inspected kit files, commit using the locally configured Git identity, add the target remote and use an ordinary push. Do not stage unrelated files from a parent directory or invent the owner's identity in Git config.

## Verify publication

Read the actual remote branch head and a representative set of files at that commit, including both `SKILL.md` files, the policy, requirements and master prompt. For a direct Git push, record local and remote commit IDs and verify they match. For publication through the GitHub connector, GitHub creates its own commit identity: verify every remote file path, mode and blob hash against the prepared source tree instead of claiming the original local preparation commit was pushed. A local commit, successful ZIP creation or permission metadata alone is not a published repository.

## Revert and skill rollback

Repository changes use ordinary revert commits, not rewritten history. Skill installation is separate from publishing. For a skill rollback, stop active jobs, inspect the private installer backup manifest, restore only the affected skill files/tree to its recorded target and remove only newly created files listed in that manifest. Preserve unrelated helpers and owner edits made after installation. Reload the actual custom Codex client and verify both identifiers resolve exactly once. Do not erase an entire shared skills root.

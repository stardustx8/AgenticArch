# Publication and recovery

Target: stardustx8/AgenticArch, branch main. Future sessions start from the current remote, START-HERE and SESSION-HANDOFF, not old transfer archives.

Read the actual branch head and worktree. Preserve concurrent changes. Run the full tests, kit checks and relevant harness checks. Publish only inspected source/docs/templates, with no private state or credentials. No force push, rewritten history, visibility change or permission bypass.

For a direct Git push, compare the resulting remote commit with the local intended commit. For GitHub connector tree/commit publication, GitHub creates its own commit identity: compare the entire path/mode/blob tree with the prepared source tree and confirm the actual branch points to it. Unreferenced trees/blobs, local commits and prepared ZIPs do not establish publication.

If main advanced, reconcile current changes before creating the integration commit. Use the current head as parent and a non-forced ref update. A rejected update is not permission to erase another session's work.

Rollback uses ordinary revert commits. Skill rollback is separate: stop/checkpoint relevant jobs, inspect the private backup manifest, restore only affected files and preserve subsequent owner edits/unshipped helpers. Do not erase a shared skill root or credential store.

Both harness packages remain on main and share the same policy. The review repository is separate; its creation and real exports need applicable scoped authorization. No license is selected implicitly by publication.

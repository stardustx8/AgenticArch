# Foreground integration coordination

The full CLM, dual-harness and quota-aware revision is being integrated now by the publishing session. It has already reconciled the concurrent CLM and research commits through 10592526 and is preserving the routing work in 294ebcb0 as well.

To avoid two sessions repeatedly replacing the same catalog and reference modules, please keep further overlapping changes on a separate branch until the integration commit and updated SESSION-HANDOFF are published. Do not discard unpublished work. This is a cooperative coordination notice, not a repository lock or change to permissions. Read the actual branch head and reconcile before publishing.

The integrating session will remove this notice as part of its verified integration commit. If that session stops, a new session should inspect the actual history and unfinished work before taking over rather than treating this notice as a permanent restriction.

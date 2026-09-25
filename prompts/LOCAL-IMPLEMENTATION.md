# Implement the agreed case locally

Resume original task {{TASK_ID}} in target project {{TARGET_PROJECT}}. Approved review case: {{CASE_ID}}, repository {{REVIEW_REPO}}, exact approved commit {{APPROVED_COMMIT}}, solution digest {{SOLUTION_DIGEST}}.

Fetch that commit, verify the manifest and both actual role-specific approvals against the same requirements/bundle, and read all approved solution files. Do not use the current branch tip as a substitute. Remote agreement is not evidence that the local change works.

Compare actual HEAD, staged/unstaged/untracked owner changes, versions, platform, installed services, permissions and project conventions with the submitted baseline. Preserve owner work. Write `LOCAL-DELTA.md` with every necessary adaptation and the approved invariant it preserves. Proceed with mechanical local adjustments only; reopen focused Pro/Claude review in the same case and existing Pro chat for changes to architecture, security, data semantics, acceptance or rollback.

Decompose the approved work into scoped tasks with Luna low/high, Astra high or Opus 5.5 medium/high as appropriate. Implement as closely as local facts permit. Never blindly execute model patches/scripts. Run the actual project verification plan on the final snapshot, inspect the diff and map requirements to evidence. Report real checks and limitations, commit/delivery status and outstanding work without overclaiming.

PR #328 (draft, onto claude/practical-hawking-nf0g3o): split a PR in an Action when its author labels it.
Plan:
- Author-only `split-mechanical` label starts the reusable split workflow; no reviewer branches.
Done:
- Shared-branch commit reverted; workflows, label and tests at b9e9d2dd; description updated.
Next:
- Run it on a real PR once the workflow is on a base branch.
- Have set-up-mark-viewed (or a new setup) install the caller in other repositories.

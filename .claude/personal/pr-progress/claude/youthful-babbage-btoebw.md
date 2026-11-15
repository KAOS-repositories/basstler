## Plan
- Apply #214's own diff (merge base to head) for the general files, not whole-file copies, since its merge base is older than main.
- Leave calls, keyword_arguments, signatures, tree_matching and their tests and datasets with #214; definition_moves uses a plain PythonComparison.

## Done
- Bootstrap, draft PR #226, item in progress.
- 106 files applied; ruff, code-rules check and review_triage, git and github tests pass.

## Next
- Full suite result, then mark ready for review once it passes.

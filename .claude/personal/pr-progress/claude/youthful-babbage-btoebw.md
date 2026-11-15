## Plan
- Move the general files from #214's branch (not cherry-pick): moves, definitions, python_source, renames, comparison, detection, triage, git/ and github/ changes, tests, datasets.
- Leave calls, keyword_arguments, signatures, tree_matching with #214; definition_moves uses a plain PythonComparison.
- Tests first: run moved tests against trimmed sources, fix on the source side.

## Done
- Bootstrap commit, draft PR #226, item recorded in progress.

## Next
- Copy the general files, trim the keyword-argument parts, run pytest and ruff.

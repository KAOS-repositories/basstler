## Plan
- Apply #214's own diff (merge base to head) for the general files, not whole-file copies, since its merge base is older than main.
- Leave calls, keyword_arguments, signatures, tree_matching and their tests and datasets with #214; definition_moves uses a plain PythonComparison.

## Done
- Bootstrap, draft PR #226, item in progress.
- 106 files applied; ruff, code-rules check and review_triage, git and github tests pass.
- Merged main (74ab12a5, the uv workspace layout of #223) at 23c6ba00: the moves, triage and rule modules, their tests and the datasets now sit under `packages/` and `test_support/`; `git/commands.py` takes main's UTF-8 `TextFile` handling over this branch's `GIT_TEXT_ENCODING`; `github/repository.py` keeps both path methods. The merge probe against main reads clean at 23c6ba00.
- At 23c6ba00 locally: ruff check and format, `basstler code-rules check` and every distribution's own test run pass.

## Next
- Read CI at 23c6ba00 (not read yet; the last green run was at 5d1e3c35), then mark ready for review.
- The ten pull requests stacked on this branch (#214, #253, #263, #265, #266 and five more) do not have this merge yet: `maintenance restack --stacked-on` stops with a git checkout error for `claude/magical-euler-j4joud` that does not reproduce by hand. Run it again, or restack them by hand.

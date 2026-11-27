## Plan
- Resolve the conflicts between this branch and `main` (0a166f91): merge `main` in, keeping the split of locations, environment and exceptions.

## Done
- Merge probe at ccc60b55 found 5 conflicting files (locations.py, actions_budget.py, plan_site/workflows.py, two tests); all resolved in the working tree.
- ruff check and format, `code-rules check` and `new-crossings origin/main` pass. Tests pass for rules, github, core, git, reviews, stack, notes, plan, review-triage, packaging, build.
- Upstream review state: not checked, no upstream is named for this clone. No review threads or comments on the pull request.

## Next
- Finish the basstler and hub test runs, commit the merge, push with `maintenance push`.
- Update the pull request description and the plan item's record; return the PR to draft.
- Ask the owner the two open questions in the PR description.

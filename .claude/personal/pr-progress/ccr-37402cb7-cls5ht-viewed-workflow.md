## Plan
- Resolve the owner's review of 3be60760 (15 new threads, 2026-11-17):
  - Rules: a field shared by several classes lives in one mixin; a field takes the most specific correct type.
  - One concept per thing: `RepositoryBranch(Branch)`; `PullRequestEnds` (base, head) for the form, the file proposal, the merge-workflow proposal and `NewPullRequest`; `PullRequestEnd(GitObject, Branch)` replacing `RestPullRequestHead`; one base for `BranchReference`/`NewBranch`; `BranchFile` for `FileCommit`/`NewFileForm`; listing filters from the ends.
  - `workflow` -> `workflow_path` (one mixin); `GitHubAccountPage` -> `NewTokenPage`, used by the plan site too.
  - Answer the questions (ValidatedJSONModel is a dataclass, why the secret read binds metadata, why file and fork steps fall to the user, per-reviewer marking).

## Done
- main merged by the maintenance pass (head e05ec18b, clean against main d576e5a9).

## Next
- Tests first, then the refactor; full suite, ruff, code-rules check; push; restack #221; reply to every thread.

## Plan
- repository-field-once: every model redeclaring `repository: Repository` inherits `HasRepository`
- `GitRepository` base in basstler.git; GitHub `Repository` subclasses it; `Remote` for a clone's remote
- `Branch[RepositoryType]` with required `repository`; merge `RepositoryBranch`; `RemoteBranch` on `Remote`; `GitHubRemote.github_repository`
- One wire-form reader/writer for `Branch`, repository from the read; REST ends from `repo`; `NewBranch` points at its commit
- `PullRequestReference` same treatment and unified with GraphQL `PullRequest` models

## Done
- Stacked on #215; draft PR #257; both items recorded in progress, repository-field-once folded in the plan

## Next
- Step 1, tests first

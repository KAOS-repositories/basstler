## Plan
- Fold repository-field-once into branch-owns-its-repository; every branch and the GraphQL pull request hold their owner

## Done
- 16 models on `HasRepository` (38f504c5)
- `GitRepository`/`Remote`/`GitHubRemote`, `Branch[RepositoryType]`, `RepositoryBranch` merged, wire forms, REST ends from `repo` (329bb0de)
- Merge-workflow refresh from the base adapted (96577cea)
- GraphQL `PullRequest` and snapshot hold `PullRequestReference` (3ab1af97)
- Full suite 3126 passed at 3ab1af97; PR description current

## Next
- CI and merge probe on 3ab1af97 not read
- User calls: merge stack settings' `Remote` with `GitHubRemote`; repository twice on `BranchReferenceRead`/`NewBranch`/`ForkFastForward`; REST pull request models' numbers

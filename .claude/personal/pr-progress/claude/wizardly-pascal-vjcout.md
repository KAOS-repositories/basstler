## Plan
- Stop hook marks the session's PR viewed once per head commit; workflow runs only on dispatch.

## Done
- Stop hook, stamp, docs; removed `--on-every-pull-request`; draft PR #275 (`release:major`).
- Review: stamp now reuses `PullRequestAtHead` (thread resolved); `SessionPullRequest` extends `HasRepository`.

## Next
- Two threads open, waiting on the reviewer: what "relate to the pull request class" means for `SessionPullRequest`, and how to tie the checkout to the repository (`Repository` carries no git runner).

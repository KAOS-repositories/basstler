## Plan
- Stop hook marks the session's PR viewed once per head commit; workflow runs only on dispatch.

## Done
- Stop hook, stamp, docs; removed `--on-every-pull-request`; draft PR #275 (`release:major`).
- Review: stamp now reuses `PullRequestAtHead` (thread resolved); `SessionPullRequest` extends `HasRepository`.

## Next
- Thread on `SessionPullRequest` is open: waiting for the reviewer to confirm what "relate to the pull request class" means.

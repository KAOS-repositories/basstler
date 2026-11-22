## Plan
- Carry #257 (repository held by every branch and pull request) onto main after #215 landed and main moved into `packages/<distribution>`.

## Done
- Merged main at 7da2b1cf: 26 conflicts resolved, main's handover and contents-access code ported to `Branch[Repository]`, `Remote`, `PullRequestEnd.commit`; new REST fixtures carry each end's `repo`.
- Merge probe clean; per-distribution suites, ruff, format and code-rules pass locally; pushed; description and plan notes updated.

## Next
- CI on 7da2b1cf is not checked; the 43 hub browser tests could not run here (no matching Chromium).
- Open for the user: unify the stack settings' `Remote` with `GitHubRemote`; REST pull request models still carry a bare number. The `needs-resolution` label is still on #257.

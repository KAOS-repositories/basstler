# Agentic loops

- The loop works on one plan item at a time. A loop over a whole plan, and the checkpoints the user sets for it, are deferred.
- The per-item loop uses built-in defaults: the seven guardrails, the protected paths and the 80% budget warning. The user sets only the on switch, the round limit and the budgets.
- A guardrail is enforced by a hook or a computed stop rule, never by instructions alone. If Claude Code has no hook for one, record the gap on the tracking issue.
- A loop ends as done only when the deterministic checks pass and the review finds nothing blocking. If the two disagree, the loop hands over to the user.
- A session the loop starts never waits for an answer. When a guardrail fires, the loop stops and comments on the pull request with the reason and what the user must decide, and only the user restarts it.
- No loop merges or releases; that stays the user's job.
- A new kind of loop is a new item, proposed on the tracking issue first.
- Test first: every item starts with a failing pytest test and lands only with it passing. Hand-overs, stop rules, hooks and GitHub reads are tested on recorded data, mocked GitHub and a mocked `claude` command, never live.
- Report everything on the pull request: every loop start, end, hand-over and failure, with the command that continues it. Nothing fails only in a log or a hook's error output.
- Decide from data: every loop decision (continue, end, hand over, which round) comes from what the loop reads back - GitHub threads, check runs, commits, checked results - never from a number the model types, from timing, or from GitHub's scheduler.
- Do not waste rounds: every session runs within its limits, and no round runs that cannot add anything (nothing blocking, no progress, no new commit).

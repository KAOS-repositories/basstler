# Agentic loops

- Loops run only for plan items.
- The user sets every checkpoint of the loop contract, once as their default and changed per item where they want: basstler suggests answers and explains each checkpoint but never fills one in, and a contract missing an answer cannot be saved.
- The seven run-time guardrails are defaults the user is shown and keeps, modifies or appends to; the result is shown back before it is saved.
- A guardrail is enforced by a hook or a computed stop rule, never by instructions alone; where Claude Code offers no hook for one, the gap is recorded on the tracking issue.
- A loop ends as done only when the contract's deterministic checks pass and the review finds nothing blocking; when the two disagree it hands over.
- A session the loop starts runs unattended: it never waits on a question. A guardrail ends the loop with a hand-over comment on the pull request saying why and what the user decides, and only the user resumes it.
- Merging and releasing stay the user's; no loop merges or releases.
- A new loop kind is a new item, proposed on the tracking issue first.
- Test-driven: every item starts with a failing pytest test that proves the missing behaviour or the bug, and lands only with it passing. Hand-overs, stop rules, hooks and GitHub reads are tested against recorded payloads, mocked GitHub and a mocked `claude` command, never live.
- Reliable: every loop start, end, hand-over and failure is reported on the pull request, with the command that continues it when one does. Nothing fails only in a log or a hook's stderr.
- Deterministic: every decision the loop takes (continue, end, hand over, which round) is computed from data the loop reads back - GitHub threads, check runs, commit SHAs, schema-checked results - never from a number a model types, and never from timing or GitHub's scheduler.
- Efficient: every session runs within the contract's budgets, and no round runs that cannot add information (nothing blocking, no progress, an unchanged head).

# Agentic loops

- A session the loop starts runs unattended: it never waits on a question, and records what would have needed one in the pull request.
- A new loop kind is a new item, proposed on the tracking issue first.
- Test-driven: every item starts with a failing pytest test that proves the missing behaviour or the bug, and lands only with it passing. Hand-overs, stop rules and GitHub reads are tested against mocked GitHub and a mocked `claude` command, never live.
- Reliable: every loop start, end and failure is reported on the pull request, where the user looks, with the command that continues it when one does. Nothing fails only in a log or a hook's stderr.
- Deterministic: every decision the loop takes (continue, stop, which round) is computed from data the loop reads back - GitHub threads, check runs, commit SHAs, schema-checked results - never from a number a model types, and never from timing or GitHub's scheduler. The same pull request state gives the same next step.
- Efficient: every session runs within explicit turn and budget limits taken from the loop's settings, and no round runs that cannot add information (nothing blocking, no progress, an unchanged head).

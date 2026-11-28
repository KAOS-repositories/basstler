# Loop mode

- The user sets every checkpoint themselves: the loop suggests answers, explains each checkpoint and answers questions about it, but never fills one in, and a contract missing an answer cannot be saved.
- The seven run-time guardrails are the defaults: the user is shown them and keeps, modifies or appends to them, and the result is shown back before it is saved.
- A guardrail is enforced by a hook, not by instructions alone; where Claude Code offers no hook for one, the skill says so and the gap is recorded on the tracking issue.
- Every loop decision - continue, end, hand over - is computed from the run log and the deterministic checker, never from a number the model types.
- A hand-over ends the iteration and tells the user why and what they decide; the loop resumes only on their answer, and never works around a denied permission.
- Merging and releasing stay the user's; no loop merges or releases.
- Test-driven: every item starts with a failing pytest test; hooks are tested on recorded payloads, GitHub is mocked.
- Built independently of agentic-loops: no item starts until the two plans are compared and merged into one.

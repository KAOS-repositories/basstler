# Loop review quality

- No item starts before agentic-loops' first end-to-end run; the items are reprioritised from what it shows.
- Every item keeps the agentic-loops rules: the user's loop contract, guardrails enforced by hooks, hand-overs on the pull request, deterministic decisions.
- A new loop kind is a new item, proposed on agentic-loops' tracking issue first.
- Test-driven: every item starts with a failing pytest test, tested against fixtures, mocked GitHub and a mocked `claude` command, never live.

# Loop review quality

- No item starts before agentic-loops' first real run (loop-end-to-end); the items are reordered by what that run shows.
- Every item follows agentic-loops' rules: built-in guardrails enforced by hooks, hand-overs on the pull request, decisions from data.
- A new kind of loop is a new item, proposed on agentic-loops' tracking issue first.
- Test first: every item starts with a failing pytest test, run on sample data, mocked GitHub and a mocked `claude` command, never live.

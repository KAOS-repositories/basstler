PR #277 (bug): an attach instruction makes a cloud session clone and register_repo_root.

Plan
- Instruction and session rules say to skip the clone and register_repo_root.

Done
- Fix and test at the first commit; affected suites pass locally (700). Draft #277, label bug.

Next
- Read CI on #277.

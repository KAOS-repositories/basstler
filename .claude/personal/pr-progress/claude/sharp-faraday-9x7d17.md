PR #278 (windows-support/windows-tests-after-merge): Windows suite on main within the tests, on PRs only for platform files.

Plan
- Tests calls windows-tests.yml on push to main; PRs path-filtered; workflow_dispatch; budget override.

Done
- Implemented at ff41a68e with tests; ruff, code rules, touched suites pass locally. Draft #278, unlabelled (patch).

Next
- Read CI on #278.

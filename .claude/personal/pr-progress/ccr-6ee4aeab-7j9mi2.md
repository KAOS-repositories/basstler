### Plan
- Read CI at cb13f576: per-distribution test job, lint, Windows setup (the Windows suite runs only once the PR is ready)
- Untangle shared test helpers so lower distributions' dev groups need fewer siblings (scratch_repository pulls in notes via setup.steps; notes' dev group lists the meta-package); propose as a new item on #151
- Mark ready only when the owner says so
### Done
- Stacked on #222; code actions generic (AppliedAction.result); SourceTree, file actions and ModuleRelocation, keeping executable bits
- One ActionPlan moved sources and tests into packages/<part>; shared helpers into test_support/basstler_testing
- Workspace pyprojects, basstler-build sibling-pin hook, uv.lock; map read from each package's folder and pyproject
- Session start: uv sync --frozen (checkout editable, release from a shallow tag clone); py -3.X candidates
- CI and every workflow install from uv.lock; rules, AGENTS.md, READMEs updated
- Resolve (cb13f576): merged base (Windows tests workflow: test moved to packages/basstler/tests, workflow syncs the lock and runs each distribution); formatted 19 lengthened imports; notes' dev group lists `basstler` (50 tests need the installed release). Merge probe clean; every distribution passes locally in its own environment
### Next
- Check CI at cb13f576, fix what it reports

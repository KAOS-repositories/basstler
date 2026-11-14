### Plan
- Read CI on 4ddeda0b: per-distribution test job, lint (uv lock --check, new-crossings prints a notice since #222's base has no workspace), Windows setup
- Untangle shared test helpers so lower distributions' dev groups need fewer siblings (scratch_repository pulls in notes via setup.steps); propose as a new item on #151
- Final PR description pass, then mark ready only when the owner says so
### Done
- Stacked on #222; code actions generic (AppliedAction.result); SourceTree, file actions and ModuleRelocation, keeping executable bits
- One ActionPlan moved sources and tests into packages/<part>; shared helpers into test_support/basstler_testing
- Workspace pyprojects, basstler-build sibling-pin hook, uv.lock; map read from each package's folder and pyproject
- Session start: uv sync --frozen (checkout editable, release from a shallow tag clone); py -3.X candidates; requirements from declarations in a checkout
- CI and every workflow install from uv.lock; rules, AGENTS.md, READMEs updated
- Local at 4ddeda0b: every distribution's suite passes; hub has only the 32 sandbox Playwright errors; meta-package last seen 681 passed
### Next
- Check CI, fix what it reports

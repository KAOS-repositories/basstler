### Plan
- Session start installs with uv sync --frozen (checkout) or from a clone of the release tag; setup.dependencies reads the installed distributions
- Windows without uv: py -3.14/-3.13/-3.12, then python, as full paths
- CI: one job per distribution with only what it lists; release and windows-setup workflows follow the paths
- Fix the notes, hub and meta-package suites; update docs and the PR description
### Done
- Stacked on #222; code actions generic; tree actions and ModuleRelocation added
- One ActionPlan moved sources and tests into packages/<part> (d9dd4b5b)
- Workspace pyprojects, basstler-build sibling-pin hook, uv.lock; map read from the workspace
### Next
- setup.dependencies and session-start install

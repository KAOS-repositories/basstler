### Plan
- `basstler.playbook` in core: component kinds, `PackageContribution`, `Playbook`, `DefaultPlaybook`, root `basstler_playbook.py`
- Move `SetupStep`/`SetupChecklist` base to core; each distribution contributes its steps
- Each distribution registers a contribution under `basstler.contributions`
- `basstler` mounts the playbook's command groups; `basstler skills build [--check]` writes hooks.json and checks skills
- Tests first for each part; ruff, docformatter, code-rules check

### Done
- Draft PR #290 opened; kickoff scope answered (only kinds with instances; hooks.json generated; root `basstler_playbook.py`)

### Next
- Write the playbook model's tests, then the model

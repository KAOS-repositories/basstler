### Plan
- Move modules and resources into packages/<part>/src/basstler (pure renames)
- Workspace root, per-package pyproject (hatch-vcs), basstler-build sibling-pin hook, uv.lock
- PackageMap reads modules/dependencies from packages; package_layout reads the namespace
- Session start: uv sync --frozen (checkout) / clone release tag; Windows py candidates
- CI per package; release and windows-setup workflows follow the paths
### Done
- Kickoff: draft PR #223, item recorded in progress; release source and pin-hook decisions made with the owner
### Next
- Map resources to their owning modules, then the move commit

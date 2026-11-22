## Plan
- Done as drafted: map imports to distributions, allow own + listed distributions' requirements + closure, report via `code-rules check` and the base comparison
- Remaining: wait for CI (all packages, Windows) and review

## Done
- Failing tests first (dataset `third-party-imports`, rules and core tests), then `LibraryCrossing`, `InstalledLibraries`, `DistributionDeclaration.libraries`
- `code-rules new-crossings` logs each new crossing through `new_import_message`
- Rule text and `AGENTS.md` updated; ruff, code-rules check and the core and rules suites pass locally
- Baseline on `main` has no library crossing (review-triage gets yaml via github, hub gets pydantic via core)

## Next
- Check CI on PR #288
- Decision to confirm: an uninstalled library counts as a crossing, so the check needs the workspace installed

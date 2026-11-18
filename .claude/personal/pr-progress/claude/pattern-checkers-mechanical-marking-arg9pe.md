## Plan
- Resolve #222's conflict with its base `fix-windows-test-failures` (in `src/basstler/maintenance/commands.py`) and hand it back for review.

## Done
- Merged the base into the branch at 293015cf; the merge probe against base commit 00660775 is CLEAN at head 293015cf.
- Resolved the import conflict, keeping the base's `LandedClosingFollowUps` import.
- `ruff check .` and `basstler code-rules fix` (no change) pass. Tests excluding `tests/plan_site` and `tests/plan/item_bootstrap`: 2425 passed, 1 skipped. Those two directories fail here only for environment reasons: libcst is not in the plugin interpreter, and Playwright is unavailable.
- All 21 review threads read as resolved at 539e4ffa; no unresolved thread. No upstream is named, so there is no upstream review.

## Next
- Read CI at 293015cf (not read yet; Windows run at 539e4ffa was cancelled).
- Owner decides whether #222 stays ready; this resolve left it as it was.

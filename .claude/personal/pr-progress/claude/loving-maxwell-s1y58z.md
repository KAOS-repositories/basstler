## Plan
- `FileUriChecker` + `AsUriFix`: `f"file://{path}"` -> `path.as_uri()`, behaviour declared changed
- Drop the `str(path)` -> `as_posix()` half: no checker can tell reliably that a string reaches command text, and #220 kept `str()` inside command lists

## Done
- Rule in the Windows section, `AGENTS.md` regenerated, checker and fix-example tests
- `code-rules fix` on main's two files reproduces #220's `file://` edits exactly

## Next
- Waits on #222 (rule-fixes) landing
- rule-fix-triage (not started) has to mark the files mechanical before the item's done condition holds

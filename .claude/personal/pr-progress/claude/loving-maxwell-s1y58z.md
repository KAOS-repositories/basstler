## Plan
- `FileUriChecker`, a fixable checker: `f"file://{path}"` becomes `path.as_uri()` (parenthesised when needed); behaviour declared changed
- Rule in the Windows section of `rules/project.py`, `AGENTS.md` regenerated
- Fix examples reproducing #220's two hand edits, plus checker tests
- Drop the `str(path)` -> `as_posix()` half: no checker can tell reliably that a string reaches command text

## Done
- Branch and draft PR #228 on #222's branch

## Next
- Tests and examples first, then the checker

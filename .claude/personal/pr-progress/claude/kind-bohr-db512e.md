## Plan
- Tests first: example `before.py`/`after.py` pairs for `TreeRemovalChecker` and `BashByNameChecker`; `DirectoryTree(ignore_errors=True)` tests.
- `DirectoryTree.ignore_errors` field; `TreeRemovalChecker` becomes a `FixableChecker`.
- Import action in `code_modification` (inverse removes the import).
- `BashByNameChecker` fixable only where an `environment` is in scope.
- Regenerate `AGENTS.md`; ruff, docformatter, `code-rules check`.

## Done
- Branch and draft PR open, stacked on #222.

## Next
- Write the failing tests.

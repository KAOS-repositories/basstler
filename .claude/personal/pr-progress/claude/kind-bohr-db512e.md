## Plan
- `DirectoryTree.ignore_errors`; `TreeRemovalChecker` and `BashByNameChecker` become fixable, with examples under `tests/dataset/rule-fixes/`.
- Statement insertion/removal actions and `ImportedName`, so a fix adds the import it needs.
- Full suite, ruff, `code-rules check`, then the PR description.

## Done
- `DirectoryTree.ignore_errors` and its tests.
- Import actions (`StatementInsertion`, `StatementRemoval`, `ImportedName`); `SourceFixer` adds each fix's imports.
- Tree-removal fix and bash fix with examples; calls the fix cannot take over (handler, no `environment`) stay reported with a message saying so.

## Next
- Full suite result; update the description with decisions; keep draft.

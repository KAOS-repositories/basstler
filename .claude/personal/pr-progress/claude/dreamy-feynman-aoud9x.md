## Plan
- Review of #288 handled: models unified (ImportStatement is an Occurrence; ModuleImport holds its statement; HasImportedModule mixin), names renamed
- Remaining: reviewer's answers on the two open threads

## Done
- Implementation, tests, rule text and AGENTS.md (CI was green before the review)
- Review round: 5 threads replied to and resolved; main merged (7dc950ed); ruff, rules check, core and rules suites pass locally

## Next
- Thread on ImportStatement.module vs imported_module: unify or keep (asked)
- Thread on ImportCrossing.importing_module: what it duplicates (asked)
- Thread "import_statement?": answered, left open
- Check CI on the new push

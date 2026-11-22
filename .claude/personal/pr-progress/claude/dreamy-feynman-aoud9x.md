## Plan
- Review of #288 handled, including the owner's `Module` ask (scope: this PR's fields only)
- Remaining: owner's look at the open "import_statement?" thread, and CI on the new push

## Done
- Implementation, tests, rule text and AGENTS.md
- Review round 1: models unified, names renamed; round 2: `basstler.module.Module` adopted for every module field this PR touches (3467c519)
- Threads: 7 of 8 resolved; ruff, rules check, AGENTS.md verify, core and rules suites pass locally

## Next
- Check CI on 3467c519
- Follow-up item (not in this PR): migrate PackageModule.name, ModuleLocation, DistributionDeclaration.modules to `Module`, and word the rule that fields meaning the same share one type (the owner's to word)
- Thread "import_statement?" stays open: answered, awaiting the owner

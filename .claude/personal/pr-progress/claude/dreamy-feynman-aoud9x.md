## Plan
- Review of #288 handled through a72b9cda: Module keeps its root, has absolute and path forms
- Remaining: owner's answer on the library question and the "import_statement?" thread

## Done
- Implementation, tests, rule text, AGENTS.md; CI green on 3467c519
- Review rounds 1-3: models unified, names renamed, `Module` adopted, relative/absolute/path forms added
- Threads: 8 of 10 resolved; ruff, rules check, AGENTS.md verify, core (224) and rules (135) suites pass locally

## Next
- Check CI on a72b9cda
- Open threads: library question on Module.path (answered: none needed), "import_statement?"
- Follow-up item (not here): migrate PackageModule.name, ModuleLocation, DistributionDeclaration.modules to `Module`; the rule that fields meaning the same share one type is the owner's to word

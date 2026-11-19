## Plan
- Tests first: every fixable rule's declared before/after example triages mechanical with a change kind named after its rule; fix plus other edits, partial fix need review; fix then reformatted is mechanical
- `SourceFixer` fixes a parsed module (text from a commit, not only a file)
- `RuleModule.fixable_rules`; review-triage depends on basstler-rules
- `RuleFixComparison` wraps the Python judgment: applies the fixes of the rules the base breaks and the head no longer does, then compares
- Profile on #220; check `basstler review-triage report 220`

## Done
- Branch from #222's head with main and #226 merged; draft #270; prototype: 106 of #220's files are UTF-8-fix-only now (notes said 107 of 129, before later pushes)

## Next
- Failing tests

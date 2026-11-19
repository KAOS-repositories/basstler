## Plan
- Rule-fix triage on #220: done; leave the draft for review

## Done
- `RuleFixComparison` + `RuleFixChange` (named after each fixable rule); review-triage depends on rules
- `SourceFixer.fix_module(module, path)`; `NodeReplacements` halves the fix cost
- #220 report: 106 of 170 mechanical (current head; 26 more carry tree/bash fixes from #227 or real edits)
- Profile: 24s baseline -> 6m08 -> 3m13; rest is libcst findall/positions

## Next
- Optional: share positions across a fix round (Action interface, touches #245) to cut the 3m
- Stack #227 to prove the tree-removal and bash-by-name files too

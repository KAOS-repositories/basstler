Plan (mechanical split and review samples, draft #241, stacked on #226):
- `basstler review-triage split-mechanical <pr>` replaces the commits since the last review with a proven mechanical commit (statement level) and a commit holding the former head's tree, and summarises the first in the description
- `report` and `mark-viewed` leave one mechanical file per rename unviewed (`--no-samples` to turn off)

Done:
- SourceRenaming, StatementMerge, MechanicalTree/Splitter/Split, MechanicalSummary, ReviewSampling; 15dee971 pushed
- 140 triage, git and command-line tests pass on Windows; local splits: CRAM 609 3435 -> 1455 lines, business_consulting 125 2757 -> 2084

Next:
- Read CI on 15dee971
- When #226 lands, retarget #241 to main
- Follow-up, not approved: renames scoped to one class's members (what keeps #125's evaluation.py renames for review)

Plan (review-triage/mechanical-file-triage, draft #213):
- Extensible basstler-review-triage distribution, CI summary, mark-viewed

Done:
- Judgments, change kinds, rename sources and outputs as extension points
- Fixed the fetch of missing commits; triaged open PRs #142, #209-#212
- Draft #213 opened, labelled release:minor; plan item records it
- Resolve (2026-11-14): merged main (tests.yml conflict, git/github module moves), 65891aa5
- Resolve: answered all 26 review threads in d9a49529; general git/GitHub classes moved to basstler.git and basstler.github, enums and class properties, TriageOutcome/FileVerdict, RenameMap.from_decisions, declaration writer with `declare` and --rename/--rejected-rename, docs/review-triage.md, bare-preposition naming rule
- Decided: ChangeKind.no_change is a class property, not a member (a memberless enum stays subclassable); viewed path is PurePosixPath; GraphQL path is GraphQLMutation.path

Next:
- Reviewer answers whether the existing of/at methods are renamed here (thread r4573303623, left open)
- CI on d9a49529 not yet read; 32 plan-site browser tests could not run locally (Chromium build mismatch)
- #214 and #215 conflict with main's reorganization; #219 is blocked behind #215
- Follow-ups: unify GraphQLMutation with GraphQLRequest/GraphQLResponse; a rename source for module moves; user runs mark-viewed locally

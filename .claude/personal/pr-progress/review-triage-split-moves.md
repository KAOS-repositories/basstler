Plan (split moves from edits, draft #241, stacked on #226):
- `basstler review-triage split-moves <pr>` replaces a PR's commits with a proven move-only commit and a commit holding every other change (tree = former head)

Done:
- MoveOnlyTree, MoveSplitter (proof by the triage, dates fixed to the head), MoveSplit.publish (force-with-lease), command, docs
- 116 triage tests pass on Windows; split of fork PR 609 checked locally (1190 new lines -> 274)

Next:
- Read CI once #226 and #241 run
- When #226 lands, retarget #241 to main
- Optional: detect moves into probabilistic_query_rules.py-like targets the triage misses today

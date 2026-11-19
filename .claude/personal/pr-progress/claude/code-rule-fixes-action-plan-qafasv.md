Plan
- Trailer `Code-Modification-Plan: <plan> basstler==<release>` + `--plan commit=plan`; replay on base; ReplayedPlanChange kind
- workspace-packages builder derived from the base tree (package_map, template readers, test-helper importers)

Done
- Merged #223 into #270 (73b990a0); all suites pass but hub's 40 browser tests (not checked)
- Replay + builder + CLI + docs (b720068f); #223: 161 -> 118 need review, 685 replayed; the 46 moved files left were edited by #223's own commits
- Replay 190 s -> 30 s; whole triage 1m48 -> 1m26

Next
- Owner: replay with the recorded release when it differs? signed, unfakeable action commits as a follow-up item?
- Read CI on #271

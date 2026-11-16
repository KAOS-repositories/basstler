Plan (Pyrefly fallback for receivers, draft #240, stacked on #238):
- Triage answers receivers basstler leaves open with pinned Pyrefly, once per PR, lazily

Done:
- RevealedReceivers (temp dir of the base commit), RevealedInference, --no-type-checker; experiment reuses it
- Import roots exclude packages nested under a non-package folder (found by mypy on CRAM)
- #967: same 12 files for review, +5.0 s (reveal 4.6 s); 253 tests pass locally at 64233df4

Next:
- Read CI on 64233df4
- Reveal time measured, left as is: on #967 probes 0.6 s, writing 2,429 files 1.1 s, Pyrefly 0.85 s, removal 0.3 s. Import closure is 752 files but takes 2.1 s to find (net loss); threaded writes save only 0.3 s

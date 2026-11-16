Plan (Pyrefly fallback for receivers, draft #240, stacked on #238):
- Triage answers receivers basstler leaves open with pinned Pyrefly, once per PR, lazily

Done:
- RevealedReceivers (temp dir of the base commit), RevealedInference, --no-type-checker; experiment reuses it
- Import roots exclude packages nested under a non-package folder (found by mypy on CRAM)
- #967: same 12 files for review, +5.0 s (reveal 4.6 s); 253 tests pass locally at 64233df4

Next:
- Read CI on 64233df4
- Reveal costs 4.6 s, mostly writing ~2,400 files; could write only what the changed files import, if it matters

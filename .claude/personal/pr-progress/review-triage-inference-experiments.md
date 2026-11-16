Plan (receiver inference experiment, draft #238, stacked on #214):
- Measure basstler's receiver inference against mypy, pyright and Pyrefly, alone and combined

Done:
- basstler+<checker> ways; enum-member Literal read as its enumeration
- #967: basstler+Pyrefly leaves the same 12 files as basstler, +1.8 s; no disputes
- CI fixes pushed: sample formatting (#214 55c271ae, merged), either-separator report paths (2eea7b7d)

Next:
- Read CI on 2eea7b7d and #214's 55c271ae
- User decides whether Pyrefly becomes a triage dependency (cost: ~1.4 s and ~100 MB worktree per base commit on CRAM, pinned version)

Plan (receiver inference experiment, draft #238, stacked on #214):
- Measure basstler's receiver inference against mypy, pyright and Pyrefly, alone and combined

Done:
- Single checker run per PR, optional cross-check (on by default)
- #214 restacked at 2d202379 (the faster triage, folded in from closed #239)
- basstler+<checker> ways from the same checker run; enum-member Literal read as its enumeration (e0ea70c0)
- #967: basstler+Pyrefly leaves the same 12 files as basstler, +1.8 s; no disputes

Next:
- Decide whether to adopt Pyrefly: it changes no verdict on #967, #608, #609
- Read CI on e0ea70c0 and on #214's 2d202379

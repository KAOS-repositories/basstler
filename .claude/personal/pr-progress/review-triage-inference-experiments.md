Plan (draft #238, experiments package, stacked on #214):
- Compare basstler's receiver inference with mypy, pyright and Pyrefly on real PRs

Done:
- Single-pass probing of every receiver, optional cross-check (on by default), fc6096a6 pushed
- #967: basstler 12 needing review, Pyrefly/pyright 14, mypy 17; no checker disputes a basstler class

Next:
- User decides: keep basstler's inference (recommended) or adopt Pyrefly
- Profile shows triage time is mostly git processes (346 git show, 178 git grep) and AST deepcopy; offered as a follow-up
- Read CI on fc6096a6

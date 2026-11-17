Plan (binding-renames, draft #253, stacked on #214):
- Detect module-level member renames (qualified path), prove each file by resolving every old token to its binding, rewrite only those in the base text
- Tests first: resolved rename mechanical; unrelated same-spelled binding swapped needs review; capture, star import, prose scope
- Measure on cognitive_robot_abstract_machine#527 from the merge base

Done:
- Branch and draft #253 opened; plan item recorded in progress

Next:
- Write failing tests and samples, then the resolver, detection and FileTriager hook
- #226 conflicts with main in src/basstler/github/repository.py, so the stack pass withheld it and #214 is not restacked onto c5473e82

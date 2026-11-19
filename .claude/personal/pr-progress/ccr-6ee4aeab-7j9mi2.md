## Plan
- Restack #223 onto #222's head, placing the files #222 and main added in their distributions.

## Done
- Merged 293015cf into the branch (25bbd5ca, pushed): review triage became basstler-review-triage, text_file and class_name went to core, fix_module and the tests use `.result`, uv.lock regenerated.
- Per-distribution tests passed locally; hub's 40 browser tests not run (no Playwright browser here).
- PR description and plan record updated.

## Next
- Read CI at 25bbd5ca (not read yet).
- Owner to confirm dropping main's interpreter-candidate session start for the uv install.
- #220 (below #222) conflicts with main; resolve it on its own branch.

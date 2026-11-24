Branch tracks the tip of the review-triage stack (#299 -> ... -> #309), plus follow-ups.

Plan
- One branch with every review-triage feature for mark-viewed; #297 and cram2 1019 mostly mechanical, no false positives.

Done
- #299-#309 as before. #310 (bug, off main): a module name a head file keeps no longer counts as renamed.
- Stacked draft PRs on #309, all release:minor: #311 re-exported import proof (carries #310's commit), #312 viewed checkpoints in notes, #313 Pyrefly receivers (port of #240).
- Shared plan/* test failures were a plan-save env missing tqdm/pyrefly; after uv sync, 191 plan tests pass on all three branches.

Next
- CI of #299-#313 and the Windows run not yet read green.
- Merge #311-#313 into claude/practical-hawking-nf0g3o after.

Branch tracks the tip of the review-triage stack (#299 -> ... -> #309), plus follow-ups.

Plan
- One branch with every review-triage feature for mark-viewed; #297 and cram2 1019 mostly mechanical, no false positives.

Done
- #299-#309 as before. #310 (bug, off main): a module name a head file keeps no longer counts as renamed.
- Pyrefly fallback (port of #240) committed 05ba7a87 on review-triage-pyrefly-receivers; review-triage tests green.
- Re-exported import proof on review-triage-reexported-imports (39d536be); viewed checkpoints in notes on review-triage-viewed-checkpoints-in-notes (32c91416).

Next
- Read basstler-package suite results for the int and ckpt branches, then push both and the Pyrefly branch as stacked draft PRs on #309.
- CI of #299-#310 and the Windows run not yet read green; update claude/practical-hawking-nf0g3o after.

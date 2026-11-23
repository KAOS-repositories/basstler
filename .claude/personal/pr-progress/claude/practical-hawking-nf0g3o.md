Branch tracks the tip of the review-triage stack (#299 -> #300 -> #301 -> #302 -> #303 -> #304).

Plan
- One branch with every review-triage feature for the mark-viewed command; prove #297 and cram2 PR 1019 mostly mechanical, no false positives.

Done
- #299 integration, #300 workspace install, #301 namespace packages, #302 attribute moves, #303 viewed-state start: CI green at their heads.
- #304 definition succession + inherited-attribute guard; cram2 1019: 244 -> 123 of 464 need review; #297 still 34 of 101.
- claude/practical-hawking-nf0g3o fast-forwarded to d578190e.

Next
- #304 CI was running at d578190e (not yet read green).
- Windows untested by hand; #262/#240/#241 not integrated; checkpoints in personal notes not done.

Branch tracks the tip of the review-triage stack (#299 -> #300 -> #301 -> #302 -> #303 -> #304 -> #305 -> #306 -> #307 -> #308).

Plan
- One branch with every review-triage feature for the mark-viewed command; prove #297 and cram2 PR 1019 mostly mechanical, no false positives.

Done
- #299-#304 as before; #305 reason line numbers, #306 property->method proofs, #307 renamed-pass reasons, #308 annotated parameter receivers (drafts, labelled).
- cram2 1019: 244 -> 111 of 464 need review; #297 still 34 of 101.
- claude/practical-hawking-nf0g3o fast-forwarded to 24ced24c.

Next
- CI of #304-#308 not yet read green.
- ~97 reasonless cram2 files unexamined; fk.dot in loops and Pose2D stay for review by design.
- Windows untested by hand; #262/#240/#241 not integrated; viewed-state checkpoints not done.

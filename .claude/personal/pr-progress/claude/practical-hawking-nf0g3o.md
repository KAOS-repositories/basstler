Branch tracks the tip of the review-triage stack (#299 -> #300 -> ... -> #308 -> #309).

Plan
- One branch with every review-triage feature for the mark-viewed command; prove #297 and cram2 PR 1019 mostly mechanical, no false positives.

Done
- #299-#308 as before; #309 per-reviewer workflow (port of #262); Windows test fixes on #299/#300 (executable bit, path compare).
- claude/practical-hawking-nf0g3o = review-triage-reviewer-workflow = fab1e874; tests, ruff, code-rules pass locally.
- cram2 1019: 111 of 464 need review; of the 97 with no reason, 25 are added files, the rest real edits; only a re-exported import respelling (1 file) is a candidate pattern.

Next
- CI of #299-#309 and the Windows run at fab1e874 not yet read green.
- Viewed-state checkpoints in personal notes; #241 split moves and #240 (Pyrefly) not integrated.

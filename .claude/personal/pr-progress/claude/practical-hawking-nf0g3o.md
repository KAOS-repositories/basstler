Branch tracks the tip of the review-triage stack (#299 -> ... -> #309), plus follow-ups.

Plan
- One branch with every review-triage feature for mark-viewed; #297 and cram2 1019 mostly mechanical, no false positives.

Done
- #299-#310 as before; #311 re-exported import proof, #312 viewed checkpoints in notes, #313 Pyrefly receivers, all stacked on #309.
- #312: without a notes branch the checkpoints stay in the clone and the run warns, naming /setup-personal-notes (826abbdc).
- CI read green at current heads of #299-#306, #308-#311 and #313 (Tests); #312 at 826abbdc was still running.
- claude/practical-hawking-nf0g3o = #309 + #311-#313 at 9cac997a; review-triage 419 pass locally.

Next
- #307 Tests failed at e9d601e0 (stack env: basstler-github metadata had no Source URL); failed job re-run, not read yet.
- Windows tests dispatched on claude/practical-hawking-nf0g3o at 9cac997a, not read yet.


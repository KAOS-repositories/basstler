## Plan
- Experiment sandbox for goal-paths on experiment/goal-paths, draft #235 (replaces #232, closed at the branch rename; never merged): seven parts, one commit series each, built straight through; ask only on real design decisions.
- After every push that changes what the plan site shows, start the site build (basstler.plan_site.build_start).
- stack-board's plan-site.yml builds from this branch during the experiment; now builds from experiment/goal-paths; set basstler_branch_or_tag back to main at accept or drop.
- Keep the sandbox merged with main while the experiment runs.

## Done
- All seven parts; a path numbers its steps and says whose move each is; the goal page shows its refresh time and re-reads pull requests (f3b9f9a0).
- Real owner steps mark-220-viewed and mark-223-viewed in review-triage; goal-paths/verdict and the goal goal-paths-decided.
- Merged main at 66d52e2c (f140f3b0, 1560 passed, probe clean). pushes-done: depends_on_pushes_done, pushes_done_at, goal pushes-done; mark-220/223-viewed wait on it.
- Experiment-mode feedback is in the experiments plan (sandbox-ownership, running-stage-rules, sandbox-site, feedback-intake widened to every plan), linked from #192.

## Next
- Write the two further goals with the user (mark-viewed pip installable; first basstler-service items).
- The owner's verdict; then stack-board back to main, feedback comment on #192, split into pull requests.
- Unverified: whether plugin Stop/PostToolUse hooks fire in cloud sessions.

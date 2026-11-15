## Plan
- Experiment sandbox for goal-paths (#232, never merged): seven parts, one commit series each, built straight through; ask only on real design decisions.
- After every push that changes what the plan site shows, start the site build (basstler.plan_site.build_start).
- stack-board's plan-site.yml builds from this branch during the experiment; set basstler_branch_or_tag back to main at accept or drop.
- Keep the sandbox merged with main while the experiment runs.

## Done
- All seven parts; a path numbers its steps and says whose move each is; the goal page shows its refresh time and re-reads pull requests (f3b9f9a0).
- Real owner steps mark-220-viewed and mark-223-viewed in review-triage; goal-paths/verdict and the goal goal-paths-decided.

## Next
- Write the two further goals with the user (mark-viewed pip installable; first basstler-service items).
- The owner's verdict; then stack-board back to main, feedback comment on #192, split into pull requests.
- #192 feedback adds: a long-running experiment goes stale against the default branch; nothing detects that an experiment is finished.
- Unverified: whether plugin Stop/PostToolUse hooks fire in cloud sessions.

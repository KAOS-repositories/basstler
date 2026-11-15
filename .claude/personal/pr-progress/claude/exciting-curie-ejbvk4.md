## Plan
- Experiment sandbox for goal-paths (#232, never merged): seven parts, one commit series each, built straight through; ask only on real design decisions.
- After every push that changes what the plan site shows, start the site build (basstler.plan_site.build_start).
- stack-board's plan-site.yml builds from this branch during the experiment; set basstler_branch_or_tag back to main at accept or drop.

## Done
- goal-path, goal-page, owner-steps (c02831ef), merged-dependencies (d46c3565), done-checks (10cca2c2), plan-goal-skill (f356a0c0).
- session-close-check (5648e595, pushed at 8d85a0e6): basstler session-close, Stop and PostToolUse hooks, plan saves settle the record.

## Next
- User decides: the block-styled-keys vocabulary test; whether real owner steps go into review-triage/plan.yaml now.
- Then use it on the real goals, accept or drop, feedback comment on #192, split into pull requests.
- Unverified: whether plugin Stop/PostToolUse hooks fire in cloud sessions (needs the plugin installed from this branch).

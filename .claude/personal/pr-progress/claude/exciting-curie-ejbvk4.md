## Plan
- Experiment sandbox for goal-paths (#232, never merged): build seven parts, one commit series each, ask for the next move after each.
- Order now: goal-path, goal-page, owner-steps, merged-dependencies, done-checks, plan-goal-skill, session-close-check.
- stack-board's plan-site.yml builds from this branch during the experiment; set basstler_branch_or_tag back to main at accept or drop.

## Done
- goal-path at 29bd414a: basstler goal set/path/next; goal mechanical-files-viewed under plans/_goals/.
- goal-page at 52f9bc90: goals on the repository index, a page per goal at <repo>/_goals/<id>/.

## Next
- owner-steps: owner moves derived from live pull request state (review and mark ready, merge) and what each releases; then stored owner steps.
- Gaps: invalid goal YAML or a cross-plan cycle stops the site build; goal page has no in-browser refresh.

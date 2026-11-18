## Plan
- Per-reviewer marking from a scheduled workflow in each reviewer's own repository (chosen design)

## Done
- ReviewedPullRequests: search a repository's open pull requests a reviewer is asked on or reviewed; mark each, going on past refusals
- review-triage mark-viewed-in-reviews command
- Reusable workflow: pull_request optional, none runs mark-viewed-in-reviews; caller template adds a schedule
- set-up-mark-viewed --in-reviews-schedule and plan_site.publication --mark-viewed-in-reviews
- README section and /setup-review-triage offer
- Merged main into #226 to clear its conflicts; this branch is stacked on it

## Next
- Read CI on 02329387
- Retarget to main once #226 lands

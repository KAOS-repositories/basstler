## Plan
- Tests first: notes remote never selected as fork; base push refused to a wider-visibility repository.
- RemoteResolution excludes the separate notes repository from fork candidates.
- Base fast-forward refuses a private-upstream to public-target push and reports it.

## Done
- Branch, draft PR 296 and plan record opened; worktree ../basstler-sync-fix (uv.lock blocked checkout here).
- Exclusion tests written and failing; fix in RemoteResolution.resolve and of_checkout in place.

## Next
- Confirm stack suite green; add of_checkout test with a configured notes remote.
- Write visibility-refusal tests, then implement.

## Plan
- Stop the merge-workflow refresh proposing from a release older than the latest, which made sessions revert each other's proposals (#280/#282).

## Done
- `PublishedReleases`, `ReleaseVersion.installed()`, guard in `merge_workflow_refresh`, tests; draft PR #284 (`bug`, patch).

## Next
- User merges #282 (latest release's `%20` text) once; await review of #284.

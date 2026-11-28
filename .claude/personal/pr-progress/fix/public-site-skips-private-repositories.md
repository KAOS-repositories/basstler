## PR #331 - The public plan site never publishes a private repository

### Plan
- Failing test: a private hub repository's plan marker appears in no built file, digest included
- Extract `RepositoryVisibilityReader` from `PushVisibilityGuard` into basstler-github
- `HubSite` takes a required `RepositoryAdmission`: `PublicRepositoriesOnly` (public build), `EveryRepository` (local build)

### Done
- Branch, draft PR #331 (bug), plan item recorded in progress

### Next
- Write the failing test

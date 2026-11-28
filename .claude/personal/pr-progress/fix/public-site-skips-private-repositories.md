## PR #331 - The public plan site never publishes a private repository

### Plan
- Owner reviews draft PR #331 (bug, patch)

### Done
- `RepositoryVisibilityReader` moved into basstler-github; the push guard holds it
- `HubSite.publication_scope`: `PublicRepositoriesOnly` in the public build, `EveryRepository` elsewhere
- `RepositorySummary.unreadable` renamed to `left_out` (owner approved)
- Tests: private plan marker in no built file, digest included; reader unit tests; pushed at 28b633cf

### Next
- CI on 28b633cf, then review comments
- local-site-open branch: pass `EveryRepository()` to its `HubSite` once this lands

## PR #331 - The public plan site never publishes a private repository

### Plan
- Owner reviews draft PR #331 (bug, patch)

### Done
- `RepositoryVisibility.read_from` in basstler-github, through `RepositoryDetailsRead`; the push guard holds the client
- `HubSite.publication_scope`: `PublicRepositoriesOnly()` (client from environment) in the public build, `EveryRepository` elsewhere
- Renames: `unreadable` to `left_out`, `or_client_from_environment` to `client_from_environment_or_this` (owner chose both)
- Review round 1: 3 threads done and resolved at 48941392; krrood `Role` thread answered, left open

### Next
- Owner decides on the krrood `Role` thread (krrood-core is not on PyPI)
- CI on 48941392
- local-site-open branch: pass `EveryRepository()` to its `HubSite` once this lands

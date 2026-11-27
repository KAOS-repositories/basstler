# Integration branches

- One integration branch per plan, integration/<plan-id>; plans are combined by merging their integration branches, never by sharing one.
- An integration branch only moves forward by merge commits: never force-pushed, rebased or reset.
- A failure on an integration branch is reported where the user sees it, as an issue and on the owning item's PR, never left silent.
- Everything is event-driven from a session's push or a workflow run: no polling and no schedule.
- Merges use the pushing session's own credential; no stored token is added for them.

## Plan
- Move each name in locations/environment/exceptions that one distribution's source alone uses, members of shared enums included (owner chose member-level), into that distribution's own `locations`/`environment`/`exceptions` module
- Names core or several distributions use stay in core
- Rewrite the rule to "once, in its own package's locations"; regenerate AGENTS.md
- Move the tests that cover moved names to the owning distribution

## Done
- Bootstrap, draft PR #297, merged main at d529812a
- Usage map: which distribution uses each name and member

## Next
- Move the whole classes, then the members, distribution by distribution; run ruff and the suite

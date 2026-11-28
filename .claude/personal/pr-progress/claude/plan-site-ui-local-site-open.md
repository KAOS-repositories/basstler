### Plan
- Discover repositories whose notes hold plans; `basstler plan-site serve` on 127.0.0.1
- Rebuild on stale page view, Refresh button
- `install-service` systemd user unit; setup recommends it for private repositories

### Done
- Branch, draft PR #330
- WIP code and tests, commit bc6f3662, local only (not pushed)

### Next
- Fix `RepositoryListingPage` (two fields read `viewer`; nest a model), rerun tests
- ruff, format, code-rules check, docs, real run; push and update the PR description
- Confirm picked defaults: port 8765, stale after 5 minutes

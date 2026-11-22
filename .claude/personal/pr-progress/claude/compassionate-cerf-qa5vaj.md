**Plan**
- Tests first for each part below
- New distribution `basstler-hub-server` (registered like `basstler-packaging`)
- Committed App manifest (JSON), read into a `ValidatedJSONModel`
- Registration page and manifest-conversion call on `basstler.github`, credentials parsed at the boundary
- Secret store: a directory of files, path from an environment variable
- Command: `python -m basstler.hub_server`

**Done**
- Branch, draft PR 294 and plan record opened

**Next**
- Write the failing tests, then the distribution skeleton

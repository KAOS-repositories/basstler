## Plan
- PyPI publishing for every distribution (#289), build tooling kept out of runtime deps.

## Done
- publish.yml (PyPI only, OIDC), PyPI-first session start, basstler-packaging model.
- 603d29aa: BasstlerFamily removed; meta package no longer depends on basstler-build or
  basstler-packaging; hook warns its settings stay backward-compatible; plan roadmap rule.

## Next
- Owner: decide whether basstler-packaging is published; register 13 PyPI trusted
  publishers and the pypi environment; README thread left open.
- CI at 603d29aa not read.

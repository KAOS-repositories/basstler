## Plan
- PyPI publishing for every distribution (#289), build tooling kept out of runtime deps.

## Done
- publish.yml (PyPI only, OIDC), PyPI-first session start, basstler-packaging model.
- 603d29aa: BasstlerFamily removed; meta package no longer depends on basstler-build or
  basstler-packaging; hook warns its settings stay backward-compatible; plan roadmap rule.

## Next
- Owner: register 13 PyPI pending trusted publishers (all free 2026-11-22) and the pypi
  environment; README thread left open. basstler-packaging is published (decided).
- CI at 603d29aa not read.

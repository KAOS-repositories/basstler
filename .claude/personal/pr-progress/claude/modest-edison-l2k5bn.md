## Plan
- PyPI publishing for every distribution (#289), one job and environment per distribution.

## Done
- publish.yml (PyPI only, OIDC), PyPI-first session start, basstler-packaging model;
  meta package free of build tooling; hook settings stay backward-compatible.
- b7d3081a: publish matrix over the build's list, environment pypi-<distribution>.

## Next
- Owner: 13 pending publishers with environment pypi-<name>; replace the basstler entry
  (environment pypi) with pypi-basstler. README thread left open.
- CI at 9d1b522c not read.

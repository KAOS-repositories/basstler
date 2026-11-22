## Plan
- Publishing is its own workflow, `publish.yml`, following the Release run, so the tests that pin `release.yml` stay as they are.
- Session start: PyPI first, the tag's lock as the fallback; the environment is used only once the package runs.
- Owner: register the 12 pending trusted publishers and the `testpypi` / `pypi` environments.

## Done
- Tests first, then `publish.yml`: build once, TestPyPI, then PyPI, OIDC only.
- LICENSE and NOTICE in every wheel and sdist; NOTICE paths follow `packages/`.
- Session start installs `basstler==<release>` from PyPI, falling back to the tag clone; one existing test changed with the owner's approval.
- README and hooks README describe both; PR description and `release:minor` label set.

## Next
- Read CI at f14412d8 (Windows included); fix what it names.
- Owner: the trusted-publisher registrations, then run `publish.yml` by hand for a tag to prove it.

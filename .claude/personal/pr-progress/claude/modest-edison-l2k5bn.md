## Plan
- Tests first: release workflow shape (OIDC, TestPyPI before PyPI); scratch-repository build (lockstep versions, sibling pins, LICENSE and NOTICE); session-start install order (PyPI, then tag clone, old environment kept on failure).
- `release.yml`: build job at the tag, TestPyPI then PyPI publish jobs, `workflow_dispatch` for an existing tag.
- LICENSE and NOTICE in every distribution; NOTICE paths follow `packages/`.
- Session start: PyPI install of the plugin's release into a fresh environment, #223's tag clone as fallback, switch only after hooks and commands load.
- Docs: README's Releasing section, SETUP.

## Done
- Planned; draft pull request opened.

## Next
- Write the failing tests.
- Owner: register the 12 pending trusted publishers and the `testpypi` / `pypi` environments.

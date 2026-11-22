## Plan
- Confirm every distribution's suite and CI pass on d5fc6b33
- Owner: PyPI pending publisher for basstler-hub-server; GHCR package public after first publish

## Done
- basstler-hub-server: configuration (env var or `_FILE`), Starlette `/health` + signed `/webhooks`, `serve`
- Dockerfile built and run locally (health 200, signed 202, bad 401, version baked, runs as nobody)
- publish.yml `publish-image` job pushing to the repository's GHCR with github.token
- `deploy-cloud-run`: APIs, Secret Manager upload, accessor grant, ghcr.io proxy repository, one instance
- README: docker run, Cloud Run, `gh webhook forward`
- app-manifest depends on service-deploy (owner's choice, posted on #200)

## Next
- Fix whatever the full suites or CI report

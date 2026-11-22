## Plan
- basstler-hub-server distribution, registered like basstler-packaging (#289)
- Instance configuration: App ID, key, webhook secret from env var or `<NAME>_FILE`
- Starlette server: `/health`, signature-checked `/webhooks`; `serve` via uvicorn on `$PORT`
- Dockerfile from uv.lock at the release version; GHCR image workflow after Release
- `deploy-cloud-run`: Secret Manager, accessor grant, ghcr.io remote repository, one instance
- Docs: docker run, Cloud Run, `gh webhook forward`

## Done
- Draft PR #295, item recorded in progress; app-manifest now depends on service-deploy (#200)

## Next
- Tests and code for the distribution and configuration

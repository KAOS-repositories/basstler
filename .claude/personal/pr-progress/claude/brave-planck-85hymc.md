## Plan
- Rebase onto main 34f58d51; resolve the conflict in core's environment.py by keeping both sides
- Move HubInstanceVariable, ContainerHostVariable and FILE_VARIABLE_SUFFIX into basstler.hub_server.environment, with their tests, as main's d052eb9e requires
- Run ruff, docformatter, code-rules check, uv lock --check and the affected suites; push through maintenance push
- Owner: PyPI pending publisher for basstler-hub-server; GHCR package public after first publish

## Done
- basstler-hub-server: configuration (env var or `_FILE`), Starlette `/health` + signed `/webhooks`, `serve`
- Dockerfile built and run locally (health 200, signed 202, bad 401, version baked, runs as nobody)
- publish.yml `publish-image` job, `deploy-cloud-run`, README
- CI green at d5fc6b33 (Python 3.12 and 3.13, ruff), read 2026-11-28

## Next
- Rebase and the environment move

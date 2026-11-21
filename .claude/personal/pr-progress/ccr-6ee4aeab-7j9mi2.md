Resolve at 58a76a3f (main at 64146fad merged in at d7360166; merge probe clean).

- Review thread on `review-triage-mark-viewed.yml` ("does this work after the uv workspaces move?"): it did not. `pip install "basstler @ git+..."` points at the repository root, now a virtual workspace. The workflow clones the ref and runs `uv sync --frozen --package basstler`, as the other workflows do. A new test requires every workflow that installs the package to do so. Answered; left open for the owner.
- Checks at d7360166 were pending (ruff, Actions usage, personal-notes setup on Windows) or skipped (Windows); CI at 58a76a3f is not read. Windows and the hub's browser tests are not checked.
- No upstream is named, so no upstream review state was read. Nothing is stacked on this branch.

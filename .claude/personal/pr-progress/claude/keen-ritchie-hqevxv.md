## Plan
- Move each name that one distribution uses (source and tests) into that distribution's own locations/environment/exceptions module; shared names stay in core

## Done
- Merged main (#290) at 362ce59e and resolved conflicts; names main's core code or lower test environments use went back to core
- CI-like per-distribution run passes (hub's 43 Playwright launch errors are sandbox-only); ruff, code-rules check, new-crossings pass
- PR #297 description current

## Next
- Read CI's pytest jobs on 362ce59e
- Owner to answer: test-only names, removing WorkspaceLocation.LOCK, renames and shared bases (WorkflowFile)

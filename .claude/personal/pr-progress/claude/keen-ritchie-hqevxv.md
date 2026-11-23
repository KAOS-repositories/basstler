## Plan
- Move each name one distribution uses (source and tests) into its own locations/environment/exceptions module; shared and shell-only names stay in core

## Done
- Bases in core declare each split enum's meaning once (ProjectFile, ActionsWorkflowFile, ...); renames REUSABLE_MARK_VIEWED and README; WORKFLOWS unified with WorkflowLocation.DIRECTORY; shell-only clause in the rule (ccc60b55)
- CI-like per-distribution run passes (hub's Playwright errors are sandbox-only); CI passed on 362ce59e

## Next
- Read CI on ccc60b55
- Owner to answer: point WorkspacePart / PackageSourceFile at WorkspaceLocation (keeps LOCK); further members repeating their subject

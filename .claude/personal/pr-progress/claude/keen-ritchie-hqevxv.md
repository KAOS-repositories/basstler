## Plan
- Move each name that one distribution's source alone uses, enum members included, into that distribution's own locations/environment/exceptions module; shared names stay in core

## Done
- Moves committed and pushed at d052eb9e (9 whole classes, 34 members, 15 exceptions; 14 new modules)
- Naming rule rewritten, AGENTS.md regenerated; ruff, code-rules check and new-crossings pass
- PR #297 description records decisions and open questions

## Next
- Read the per-distribution suite results and record them in the PR
- Read CI on #297
- Owner to answer: test-only core names, and member names that repeat their class's subject

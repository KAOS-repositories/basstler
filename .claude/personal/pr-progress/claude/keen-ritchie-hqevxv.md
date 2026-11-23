## Plan
- Move each name that one distribution's source alone uses, enum members included, into that distribution's own locations/environment/exceptions module; shared names stay in core

## Done
- Moves pushed at d052eb9e; ClaudeCodeVariable kept whole in core at e4883780 (a meta-package test reads it as a set)
- Every distribution's tests pass in the sandbox (affected ones rerun at e4883780); ruff, code-rules check, new-crossings pass
- PR #297 description records decisions, results and open questions

## Next
- Read CI on #297
- Owner to answer: test-only core names, and member names that repeat their class's subject

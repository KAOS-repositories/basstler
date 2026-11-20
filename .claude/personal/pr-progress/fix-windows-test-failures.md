Plan (Windows test failures, draft #220, off main):
- Make the suite pass on Windows; each non-Windows bug found on the way is its own PR off main

Done:
- Portability code rules, POSIX paths, BashPath, CRLF rows, LICENSE LF, pinned initial branch; install-lock liveness, session-start paths, gh hidden from PATH, 22 gh/bash stub tests skipped on win32; restored the lost unmodelled-items handler
- Windows run 466 failed + 196 errors -> 1 failed, 2827 passed, 22 skipped (42fc3148)
- Merged main at ff84098e (took PlanSaveScript and Manifest.text; read the new hand-over text as UTF-8); merge probe CLEAN at fed0d1b8
- Review: the three checkers use libcst through SourceModule (libcst>=1.8 added on the user's say-so); the collector is a dataclass with a classproperty; checker tests read expected lines from `# violation` marks in the snippets (MarkedSnippet); five threads answered and resolved
- Locally at fed0d1b8: ruff, ruff format, `basstler code-rules check` clean; tests/code_rules (59) pass. The full suite has not run clean in one go since libcst was installed; no Windows run since e6871da0

Next:
- Read CI on fed0d1b8; the Windows job first runs when #220 is marked ready
- #222 (claude/pattern-checkers-mechanical-marking-arg9pe) conflicts in 7 files, including the three checkers rewritten here: its owner decides; #270, #271, #245, #228 and two more wait behind it
- Merge #234 (python3.14 shim failure)
- Follow-up: convert the other seven ast modules in src/ to libcst

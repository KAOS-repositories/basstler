Plan (Windows test failures, draft #220, off main):
- Make the suite pass on Windows; each non-Windows bug found on the way is its own PR off main

Done:
- Portability code rules, POSIX paths, BashPath, CRLF rows, LICENSE LF, pinned initial branch
- Install-lock liveness, session-start paths, gh hidden from PATH, 22 gh/bash stub tests skipped on win32
- Restored the lost unmodelled-items handler (failed CI on Linux); hard-link mirror on Windows
- Windows run 466 failed + 196 errors -> 1 failed, 2827 passed, 22 skipped (42fc3148)
- Merged main twice (conflicts in review_triage/outputs.py and its test); read 10 more bare read_text() calls from main as UTF-8; merge probe CLEAN at e6871da0 against 98767e4d
- After the merge only 254 targeted tests were run on Windows (all passed); the full suite was not re-run - it needs hours here

Next:
- Read CI on e6871da0; the Windows job first runs when #220 is marked ready
- #222 (claude/pattern-checkers-mechanical-marking-arg9pe) conflicts with this branch in 5 files; its owner resolves it, and #270, #271, #245, #228 and two more wait behind it
- Merge #234, after which the last local failure (python3.14 shim) passes
- Optional follow-up PR, not approved: make the gh command overridable so stubs work on Windows

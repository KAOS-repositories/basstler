Plan (Windows test failures, draft #220, off main):
- Make the suite pass on Windows; each non-Windows bug found on the way is its own PR off main

Done:
- Portability code rules, POSIX paths, BashPath, CRLF rows, LICENSE LF, pinned initial branch
- Install-lock liveness, session-start paths, gh hidden from PATH, 22 gh/bash stub tests skipped on win32
- Restored the lost unmodelled-items handler (failed CI on Linux); hard-link mirror on Windows
- Windows run 466 failed + 196 errors -> 1 failed, 2827 passed, 22 skipped (42fc3148)
- Skip-unusable-interpreter fix split out as draft #234

Next:
- Read CI on 42fc3148; the Windows job first runs when #220 is marked ready
- Merge #234, after which the last local failure (python3.14 shim) passes
- Optional follow-up PR, not approved: make the gh command overridable so stubs work on Windows

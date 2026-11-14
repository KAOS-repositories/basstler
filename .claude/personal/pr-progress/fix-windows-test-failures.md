Plan (Windows test failures, draft #220, off main):
- Fix the Windows-only causes of the suite failures, each with a test that fails on Linux CI first where possible

Done:
- Three portability code rules, python3 stub, POSIX paths, file URLs, BashPath, helper backslash, CRLF rows,
  LICENSE LF, pinned initial branch; Windows run 466 failed + 196 errors -> 39 failed, 0 errors (cee36b88)

- windows-tests.yml runs the whole suite on windows-latest for PRs ready for review, skips drafts

Next:
- The Windows job first runs when #220 is marked ready; read which fail there and whether Defender blocks stubs
- Decide how to stub gh/bash on Windows (.exe launcher vs shutil.which in production), ~20 tests
- Lock liveness with MSYS vs Windows PIDs (~6), Windows environment session-start tests (~5), gh login leak

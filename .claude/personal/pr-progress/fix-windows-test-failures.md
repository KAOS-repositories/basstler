Plan (Windows test failures, draft #220, off main):
- Make the suite pass on Windows; each non-Windows bug found on the way is its own PR off main

Done:
- Portability code rules, POSIX paths, BashPath, CRLF rows, LICENSE LF, pinned initial branch
- Install-lock liveness, session-start paths, gh hidden from PATH, 22 gh/bash stub tests skipped on win32
- Restored the lost unmodelled-items handler (failed CI on Linux); hard-link mirror on Windows
- Windows run 466 failed + 196 errors -> 1 failed, 2827 passed, 22 skipped (42fc3148)
- Merged main again at ff84098e (conflicts in plan/item_bootstrap/documents.py, plan/model.py, tests/setup/test_personal_notes.py: took main's PlanSaveScript and Manifest.text); read the text main's new plan hand-over code touches as UTF-8; merge probe CLEAN at b15fa66b
- Review (tree_removal.py): the three checkers now use libcst, not ast, through SourceModule, so shutil and subprocess are resolved through the file's imports; libcst>=1.8 added as a dependency on the user's say-so; both threads answered and resolved
- Locally at b15fa66b: ruff, ruff format and `basstler code-rules check` clean; tests/code_rules, tests/plan, test_dependencies and test_document_references pass. The full suite was last run before the libcst environment was installed, so it has not run clean in one go; the full Windows suite was not re-run

Next:
- Read CI on b15fa66b; the Windows job first runs when #220 is marked ready
- #222 (claude/pattern-checkers-mechanical-marking-arg9pe) now conflicts in 7 files, including the three checkers rewritten here (bash_by_name, locale_encoding, tree_removal): its owner decides how its fixes sit on the libcst versions; #270, #271, #245, #228 and two more wait behind it
- Merge #234, after which the last local failure (python3.14 shim) passes
- Convert the other seven ast modules in src/ to libcst: a follow-up, not in this PR
- Optional follow-up PR, not approved: make the gh command overridable so stubs work on Windows

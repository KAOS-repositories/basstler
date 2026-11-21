PR https://github.com/KAOS-repositories/basstler/pull/219 (draft, base main)

Plan
- Plan site builds its token form with FineGrainedTokenForm; drop its own enums and token_page.

Done
- RepositoryPermission.ACTIONS, SiteRepository.token_form_url on FineGrainedTokenForm.
- Merged main (5667d3e1) into the branch: the conflict in site_repository.py and test_site_repository.py was main moving PermissionLevel to basstler.github.permission_level. Kept this branch's FineGrainedTokenForm code and imported PermissionLevel from there; the test only changed its import.
- At head d0a9ffa6: merge probe against main CLEAN; ruff check, ruff format and basstler code-rules check pass; tests/plan_site, tests/github, tests/review_triage 855 passed, 43 Playwright browser tests errored because the chromium build is missing in this session (not caused by the change).
- Not checked: CI on d0a9ffa6 (just pushed); docformatter (tqdm missing here, edits touched no docstring); upstream review (no upstream is named).

Next
- Wait for CI and review; no review threads so far.

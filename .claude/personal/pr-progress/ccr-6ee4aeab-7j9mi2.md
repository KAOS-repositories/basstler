## Plan
- Resolve #223: bring it level with main now that #222 and #220 have merged, and answer its three review threads.

## Done
- Merged main into the branch (4e9345f3, pushed): main's 84 added files were placed by package_map, its changes to moved files applied, hub now depends on basstler-review-triage, the Windows workflow keeps main's shards and path filters, and the shard options are the plugin basstler_testing.suite_shard.
- Moved PathAnsweringClient and refusal to test_support, since the github and review-triage tests both use them.
- Local tests at 4e9345f3: every distribution passes; hub has 443 passed and 43 errors, all Playwright unable to launch Chromium here, so its browser tests were not checked. ruff, ruff format, uv lock --check and code-rules check pass.
- PR description and plan record updated; the stale blocker is cleared. The merge probe against main reports no conflicts.

## Next
- Read CI at 4e9345f3 (not read yet), including the sharded Windows job, which was not run here.
- Owner to confirm dropping main's interpreter-candidate session start for the uv install.
- Follow-up: untangle the shared test helpers so lower distributions' dev groups stop listing the ones above them.

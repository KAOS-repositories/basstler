Plan
- Contract test: a distribution's dev group lists no basstler distribution outside its runtime requirements
- Split test_support helpers by layer (scratch_repository, maintenance/fork, repository_fixtures)
- Move the 7 tests that import a higher distribution up to its owner
- Trim dev groups, uv lock, run each distribution alone in a fresh environment
Done
- Bootstrap, draft PR #287
Next
- Contract test, then the helper split

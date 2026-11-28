### Plan
- Pointer `.claude/personal/notes-repository` (git config format) on origin's notes branch
- Session start follows it once, records it in `.git/basstler/notes-repository`
- Shell and Python resolve: git config > env > recorded pointer > origin; one hop, cycles refused
- Setup writes the pointer on origin when the remote is separate

### Done
- Branch, draft PR #333, plan item recorded in progress

### Next
- Tests first: pointer from a fresh clone, config overrides it, cycle refused, unreadable reported
- Shell resolver, session start, check-setup, Python mirror, setup write

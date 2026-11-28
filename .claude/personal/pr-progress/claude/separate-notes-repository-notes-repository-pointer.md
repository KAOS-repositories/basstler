### Plan
- Pointer `.claude/personal/notes-repository` (git config format) on origin's notes branch
- Session start follows it once, records it in `.git/basstler/notes-repository`
- Shell and Python resolve: git config > env > recorded pointer > origin; one hop, cycles refused

### Done
- Draft PR #333; implementation and tests at ab7952e0; core/notes/basstler/stack suites green
- Setup writing the pointer posted as a follow-up on #291

### Next
- Owner review; pilot on business_consulting (merge its two notes branches, owner approves the diff)

# A private project's separate notes repository - standing rules

- The project's code never leaves the project's repository: nothing basstler pushes to a notes repository is a branch of the project.
- A separate notes repository holds only notes branches; it is never a fork, and never a candidate for one.
- Every fix lands as its own basstler pull request with tests, and the business_consulting KPI plan (KAOS-repositories/business_consulting-notes, kpi-collection) is the pilot that checks it.
- When team-repository's plan store lands, the separate notes repository migrates to it rather than growing a second store.
- A pointer on origin's notes branch names the notes repository; session start follows it for every notes read and write. Explicit claude.personalNotesRemote or CLAUDE_PERSONAL_NOTES_REMOTE still wins; one hop, cycles refused, an unreadable pointer reported. Pilot: merge business_consulting's two notes branches after a file-by-file diff the owner approves.

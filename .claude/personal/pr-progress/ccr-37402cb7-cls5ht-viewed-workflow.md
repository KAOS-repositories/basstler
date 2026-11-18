## Plan
- Wait for the owner's answers on the open threads, then carry them out.

## Done
- 8457b9be: resolved the review of 3be60760. Shared fields now have one definition each: RepositoryMember, RepositoryWorkflow, RepositoryBranch, PullRequestEnds/Opening, BranchFile, PullRequestEnd as a Branch, one RepositoryDetails, and NewTokenPage. Added two rules (shared field in one mixin; most specific type). 6 threads resolved, 10 replied and left open.
- Checked at 8457b9be: clean against main d576e5a9. Local suite 3085 passed (2 tag-only failures, as on main). CI: py3.12, ruff, Actions usage and Windows passed; py3.13 was still running.
- Stacked claude/eager-archimedes-98og6c merged it (token-page conflict resolved) and was pushed; the restack now reads up-to-date.

## Next
- Owner decisions: merge ListedPullRequest into RestPullRequestSummary? Git reference base? Drop the AddFile/ReplaceFile fallbacks? Fork sync option (2)? Type the secret read? Plan items for per-reviewer marking and for the repository-field cleanup.

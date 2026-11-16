## Plan

Resolve the owner's review of 1c54d6ff inside this PR (remodel here; on a fork, propose upstream).

## Done

- 7ec5fc52: addresses on Repository, BasstlerProject, PrefilledForm/UrlQueryParameter, GitObject/EncodedContent/FileCommit, RepositoryRead/SettingWrite, user_steps, ActionsSecret, fork proposal upstream, tests strengthened.
- 3be60760: two new code rules (+ HandBuiltAddressChecker), Repository.actions_secret_path with path_on on top (user's choice), Repository.from_name_or_remote, docs/skill for the fork contract.
- Replied to all 83 threads; 71 resolved, 12 open for the owner.
- Description updated; clean with main at 66d52e2c.

## Next

- Read CI's pytest jobs on 3be60760.
- Owner's answers on the 12 open threads (Specification design, wider remodel, per-reviewer marking plan item, recommending the setup step).
- Carry the fix into #219 (GitHubAccountPage, from_requested_use, SiteRepository token pages).

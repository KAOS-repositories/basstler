## Plan

Resolve the owner's 83-thread review of 1c54d6ff here (user chose the remodel in this PR; on a fork, propose upstream). One commit per step, tests first:

1. Paths: hand-built REST/web addresses move onto `Repository`; the token page onto `GitHubAddress`.
2. `BasstlerProject`: repository from package metadata, its name and default branch, replacing `BASSTLER_REPOSITORY`, `README_BRANCH`, hard-coded "basstler"/"main".
3. Forms: `UrlQueryParameter` and `PrefilledForm` bases; one-pass truncation; `Branch` for base/head.
4. Contents API: `GitObject` and `EncodedContent` bases; aliased full names; `FileCommit` replaces the commit dicts; `propose` split; listing reuses `RestPullRequestSummary`.
5. Settings: `RepositoryRead[Resource]` and generic setting writes, each naming its manual user step; `RepositoryDetails` relates to `Repository`.
6. Shared user steps in `basstler.github.user_steps`; the plan site's token steps reuse them.
7. `ActionsSecret` base; token creation/storage steps live on the token.
8. Fork: workflow proposed on the parent from a fork branch; docs and skill follow.
9. Small threads: refusal enum, renames, `named_or_remote` onto `Repository`, weak tests.
10. New code rule (REST models tied to their domain class; addresses on the class they address), `AGENTS.md` regenerated.
11. Reply to every thread; resolve only those done.

## Done

- #215 and #219 restacked on main 73801cd6; #215 clean at 7f6928a5.

## Next

- Step 1.

Plan (draft #259, off main, bug):
- Mark only files GitHub lists for the PR, and nothing once its head moved since the triage

Done:
- FilesPage query + models; PullRequestHeadMoved; unlisted files skipped with a warning (6196fe50)
- 4 marking tests, 2 proven failing without the fix; tests/review_triage 40 passed, ruff and code-rules pass

Next:
- Read CI on 6196fe50
- After merge, merge main into review-triage-binding-renames and re-run mark-viewed 527

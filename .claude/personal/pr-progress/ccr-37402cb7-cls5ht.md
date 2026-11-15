## Plan
- Resolve #213: merge main, answer the open review threads, carry the fix into the stacked pull requests.

## Done
- Merged main into ccr-37402cb7-cls5ht (conflicts in github/exceptions.py and pull_request_models.py resolved: shared GraphQLErrorsReturned kept beside UpstreamReadError); pushed 06ea0772.
- Renamed ChangeSize.of to from_file_changes (thread resolved); added :return: to the three review-triage commands (threads replied, left open).
- ruff and code-rules pass; 2823 tests pass, 2 retired-skill tests fail on the installed major version 0 (not caused by this change, not checked on main).

## Next
- Reviewer confirms the "missing return" reading; decides on the other bare `of`/`at` names.
- Stacked #215 and #214 conflict with this branch (#219 behind #215): resolve on those branches.
- Read CI at 06ea0772; no upstream is named, so upstream reviews were not read.

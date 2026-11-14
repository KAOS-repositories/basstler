Plan (review-triage/mechanical-file-triage, draft #213; follow-ups draft #214, #215):
- #213: extensible basstler-review-triage distribution, CI summary, mark-viewed
- #214: keyword arguments; module, definition and file-path moves; relative imports;
  the modules definitions move between
- #215: mark viewed on every PR or on demand; set-up-mark-viewed; README; skill

Done:
- #214: modules only gaining/losing moved definitions mechanical, moves out of moved
  modules detected (40c94a42); #217 63/98 mechanical, #210 232/249; 2760 tests green
- #215: set-up-mark-viewed names an open PR carrying the workflow (lowest stacked),
  links the filled-in PR form; one token for plan site and mark-viewed; 2771 green

Next:
- User: review and merge #213, #214, #215 (merging left to the user); re-run
  set-up-mark-viewed afterwards
- Follow-up suggested: plan site onto github.token_form (needs a test change)
- Possible: path literals following a moved directory (#210 locations.py)

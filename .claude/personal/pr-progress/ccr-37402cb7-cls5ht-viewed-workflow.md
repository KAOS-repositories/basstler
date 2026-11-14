Plan (review-triage/mechanical-file-triage, draft #213; follow-ups draft #214, #215):
- #213: extensible basstler-review-triage distribution, CI summary, mark-viewed
- #214: keyword arguments; module, definition and file-path moves; relative imports;
  the modules definitions move between; class replaced by a subclass
- #215: mark viewed on every PR or on demand; set-up-mark-viewed; README; skill

Done:
- #214 (026ccf19): #213's review answers merged in; class replaced by a subclass of
  moved-down members; section headers optional; shared git lookups. #217 72/98 in
  5.8 s, #210 233/249 in 10.6 s, memory flat; 2815 tests green
- #215: set-up-mark-viewed names an open PR carrying the workflow (lowest stacked),
  links the filled-in PR form; one token for plan site and mark-viewed; 2771 green

Next:
- #215 still lacks #213's review answers (merge them in when next touched)
- User: review and merge #213, #214, #215; re-run set-up-mark-viewed afterwards
- Follow-up suggested: plan site onto github.token_form (needs a test change)

Plan (review-triage/mechanical-file-triage, draft #213 merged; follow-ups draft #214, #215):
- #213: extensible basstler-review-triage distribution, CI summary, mark-viewed (merged)
- #214: keyword arguments; module, definition and file-path moves; relative imports;
  the modules definitions move between; class replaced by a subclass
- #215: mark viewed on every PR or on demand; set-up-mark-viewed; README; skill

Done:
- #214 (026ccf19): #213's review answers merged in; class replaced by a subclass of
  moved-down members; section headers optional; shared git lookups
- #215 (1c54d6ff): main merged in (10 conflicts: TriagePublication, PullRequestChangesReader,
  github.* module moves, GraphQLErrorsReturned); CLAUDE_CODE_REMOTE defined in the shell
  configuration (CI failure of test_skill_documents); test_package_contract back to main's.
  Merge probe against main fbb29c45: clean. Local suite 2903 passed; CI on 1c54d6ff not read

Next:
- Read CI on 1c54d6ff
- #219 (stacked on #215) conflicts with the resolved #215 in token_form.py, site_repository.py,
  user_steps.py, tests/plan_site/test_site_repository.py: its owner resolves or asks
- User: review and merge #214, #215; store the token; re-run set-up-mark-viewed afterwards
- Follow-up suggested: plan site onto github.token_form (#219)

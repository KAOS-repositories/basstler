Plan (binding-renames, draft #253, stacked on #214):
- Prove renames by resolving bindings: module members, class methods and attributes
- Ship scripts/review-triage.sh so anyone can run the triage on any repository

Done:
- Members, attributes, star imports followed through the commit, repeated imports, optional prose words; 177 triage tests pass
- Pushed d2c3af61; CRAM 527 from the merge base: 81 of 335 need review on #253 alone
- Markdown code blocks split off as #254, stacked on this

Next:
- Read CI on #253
- Word-level renames still accept a file overriding a stdlib method (run -> execute)
- Unresolved receivers, keyword parameters; business_consulting #125 evaluation.py check

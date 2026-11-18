Plan (binding-renames, draft #253, stacked on #214):
- Prove renames by resolving bindings: module members, class methods and attributes
- Ship scripts/review-triage.sh so anyone can run the triage on any repository

Done:
- Members, attributes, star imports, repeated imports, optional prose words
- Unused added or removed imports need review; unparsable modules leave definitions unknown
- Pushed 61f0f5ef; CRAM 527: 99 of 440 need review from merge base, 69 of 378 since 203c33f2 (309 marked viewed)
- Markdown code blocks split off as #254, stacked on this

Next:
- Restack #254 onto 61f0f5ef; read CI on #253
- Word-level renames still accept a file overriding a stdlib method (run -> execute)
- Unresolved receivers, keyword parameters; business_consulting #125 evaluation.py check

Plan (binding-renames, draft #253, stacked on #214):
- Prove renames by resolving bindings: module members, then class methods and attributes
- Ship scripts/review-triage.sh so anyone can run the triage on any repository

Done:
- Module members and class attributes (self, cls, class name, subclasses, super(), override and stdlib checks); 175 triage tests pass
- Pushed 71621817; the script, run from the branch URL on CRAM 527 with --mark-viewed: 90 of 335 need review, all 245 mechanical marked viewed

Next:
- Read CI on #253
- Word-level renames still accept a file overriding a stdlib method (run -> execute); fix separately
- Unresolved receivers, keyword parameters; business_consulting #125 evaluation.py check

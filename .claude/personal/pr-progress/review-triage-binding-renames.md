Plan (binding-renames, draft #253, stacked on #214):
- Module-level member renames proven by binding resolution (done in this PR)
- Later: methods and attributes through self/cls and receivers; keyword parameters

Done:
- MemberRenameDetection (mutual-dominance pairing) and MemberRenamer (resolve, rewrite base, capture, prose rule); 168 triage tests pass
- CRAM 527 from the merge base: 333 to 90 of 335 files need review; mechanical files audited for ROS/robokudo Pose
- #214's 4d13d564 merged in and pushed through maintenance push

Next:
- Read CI on #253
- business_consulting #125 evaluation.py check (the item's recorded done-check), not run yet

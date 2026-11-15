# goal-paths - standing rules

- A step's order and state are computed from the plans and live pull request state, never stored a second time.
- No command taken from the notes branch runs anywhere but `basstler plan check`, and never in the site build.
- Every part ships tests against a fixture copy of the #220 runbook's plans.
- While the experiment runs, each commit belongs to one future item, so the split moves commits and never untangles them.

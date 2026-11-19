<!-- BEGIN-PR-PROGRESS -->
**Plan**
- Merge the moved base `fix-windows-test-failures` (e6871da0) into this branch; keep the base's listed-file marking and read its new documents through `TextFile`.

**Done**
- Merged at 6ed0232c and pushed; merge probe clean against the base. Ruff, format and the suite pass locally (2580 passed), except `tests/plan_site` and `tests/plan/item_bootstrap`, which were not run.
- Item blockers and the pull request description updated. The PR stays ready for review, as the user chose.

**Next**
- Read CI at 6ed0232c.
- #220 (the base) conflicts with `main` in `plan/item_bootstrap/documents.py` and `plan/model.py`, and is withheld by the maintenance pass; resolve it on its own pull request, then run the pass again.
<!-- END-PR-PROGRESS -->

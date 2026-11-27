PR #328 (draft, onto claude/practical-hawking-nf0g3o): share a split on its own branch.
Plan:
- `--share-split` on report and mark-viewed pushes the split to basstler/mechanical-split/<n> and links the remaining commit.
Done:
- Implemented and tested at a4fe7cd1; draft PR opened, labelled release:minor.
Next:
- Try it on a real pull request (e.g. cram2 1077) against a fork the reviewer owns.
- Optional: a label-triggered Action that runs split-mechanical for authors.

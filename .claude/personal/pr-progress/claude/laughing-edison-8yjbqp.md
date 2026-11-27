PR #328 (draft, onto claude/practical-hawking-nf0g3o): split after every push by adding M/P/S/R commits.
Plan:
- Additive split (M cumulative, P/S per push, R head); Action on label + every push while labelled.
Done:
- Implemented and tested at 10d47e44; description updated.
Next:
- Confirm on a test PR that GitHub diffs a merge commit against its first parent.
- Run the Action for real once on a default branch; installing the caller elsewhere.

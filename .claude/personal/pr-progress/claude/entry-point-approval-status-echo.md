### Plan
- Review thread r4619570035 (named regex parts, cleanest design): resolved in c5bee013.
### Done
- Added `basstler.regular_expression` (StrEnum atoms, CharacterSet, composable RegularExpression); rewrote every pattern in src/ and tests/; added bash syntax enums and `basstler.yaml_syntax`.
- Added the rules "patterns read as named parts" and "no pattern text" (HandWrittenPatternChecker). The user approved exempting `upstream_reviews/helper/fetch.py`.
- Full suite at c5bee013: 3152 passed. 2 failures are the version-tag tests, which fail on a tagless clone without the change too. ruff, format, code-rules, agents-md: clean.
- Pushed; description updated; labelled release:minor; replied inline and resolved the thread. PR stays a draft.
### Next
- CI on c5bee013 not read yet.

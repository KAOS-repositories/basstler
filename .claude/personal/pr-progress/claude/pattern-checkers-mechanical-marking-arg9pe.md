## Plan
- Make #222 pass Windows CI: its 19 failures at `54f7ebb5` came from `TextFile` keeping CRLF that Git for Windows checks out.

## Done
- Merged main (`abd1b012` is in the head) and the earlier conflicts with `ReferenceTo` replacing `SourceModule`.
- `TextFile.read` ends every line with `\n`, `write` keeps the text's endings as given; `.gitattributes` checks text out as LF (agreed with you). Test first: the CRLF read test failed before the change.
- Pushed `f7a288b5`; suite passes locally except the Playwright tests; description updated.

## Next
- Read Windows CI at `f7a288b5`.
- Carry the fix into the stacked pull requests once `maintenance restack` works.

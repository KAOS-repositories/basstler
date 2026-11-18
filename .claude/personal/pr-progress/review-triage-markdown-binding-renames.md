Plan (markdown-binding-renames, draft #254, stacked on #253):
- Resolve binding renames in Markdown python code blocks and MyST notebook cells

Done:
- Blocks read as one module, resolved like a Python file; {code-cell} cells read as code after their :tags: or --- options; 178 triage tests pass
- Pushed dba4f8b4; the script from this branch on CRAM 527 with --mark-viewed: 58 of 335 need review, the four self_assessment exercises now viewed

Next:
- Read CI on #254
- Indented code blocks in list items; the domain_models READMEs still in review

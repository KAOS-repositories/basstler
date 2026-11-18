Plan (markdown-binding-renames, draft #254, stacked on #253):
- Resolve binding renames in Markdown python code blocks and MyST notebook cells

Done:
- Blocks read as one module, resolved like a Python file; {code-cell} ipython3 cells read as code; 178 triage tests pass
- Pushed b911dee8; the script from this branch on CRAM 527 with --mark-viewed: 62 of 335 need review, all 273 mechanical marked viewed

Next:

- Read CI on #254
- Indented code blocks in list items; the self_assessment exercises and domain_models READMEs still in review

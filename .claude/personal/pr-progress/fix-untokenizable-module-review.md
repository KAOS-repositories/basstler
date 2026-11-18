Plan (unparsable modules in review triage, draft #263, off review-triage-binding-renames):
- A Python module that does not parse needs review instead of crashing the triage

Done:
- Found the crash: merge-commit versions of two PR 527 test modules hold conflict markers
- Rename sources skip such modules; PythonComparison sends them to review (ee918f35)
- Report on PR 527 completes; 235 review_triage tests, ruff and code-rules pass

Next:
- Read CI on ee918f35
- Run docformatter through the pre-commit hook where it is installed

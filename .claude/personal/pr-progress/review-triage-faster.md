Plan (speed up the review triage, draft #239, stacked on #214):
- Cut git process starts and tree copies without changing any verdict

Done:
- Batched file reads (cat-file --batch), one class-header grep for subclasses, one ls-tree per commit, re-parse instead of deepcopy
- cram2#967 triage 65.2 s -> 17.5 s; identical verdicts on #967, #608, #609 (11b1d261 + follow-up)

Next:
- Read CI on #239
- When #238 and #239 meet, keep both DatasetLocation entries (RECEIVER_INFERENCE, CLASS_HEADERS) in tests/constants/paths.py

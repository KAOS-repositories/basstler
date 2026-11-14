# review-triage — standing rules

- A file is mechanical only when equality is proven after the allowed normalisations; anything unparsable or unknown needs review.
- A runtime string literal is never rewritten by a rename.
- A rule fix counts as mechanical only when recomputing it from the base reproduces the head; who or what made the change is never trusted.
- Every fix declares whether it preserves behaviour or which behaviour it changes, and the examples it declares are tested automatically.

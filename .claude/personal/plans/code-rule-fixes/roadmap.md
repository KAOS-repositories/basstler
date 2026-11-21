# code-rule-fixes — standing rules

- A file is mechanical only when equality is proven after the allowed normalisations; anything unparsable or unknown needs review.
- A rule fix or recorded modification counts as mechanical only when recomputing or replaying it from the base reproduces the head; who or what made the change is never trusted.
- Every fix declares whether it preserves behaviour or which behaviour it changes, and the examples it declares are tested automatically.
- Analysis never imports the code it analyses: checkers, fixes and the triage parse source with libcst or ast; class hierarchies and signatures come from static readers such as DefinitionIndex, never from live modules.
- A commit records the code modification plan it applied in a Code-Modification-Plan trailer naming a plan the triage owns and rebuilds on the base; only commits that predate it are named on the command line.
- A refactoring refuses and lists every place it cannot resolve; it never guesses.

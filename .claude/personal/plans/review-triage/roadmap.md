# review-triage — standing rules

- A file is mechanical only when equality is proven after the allowed normalisations; anything unparsable or unknown needs review.
- A runtime string literal is never rewritten by a rename.
- Analysis never imports the code it analyses: checkers, fixes and the triage parse source with libcst or ast; class hierarchies and signatures come from static readers such as DefinitionIndex, never from live modules.

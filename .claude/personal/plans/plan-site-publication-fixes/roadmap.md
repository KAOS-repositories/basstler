# plan-site-publication-fixes — standing rules

- Each item is one bug pull request off main with a failing test first, labelled bug.
- Publication reports a problem before the user takes a step it would make useless.
- The build reads each listed repository's visibility from GitHub. A private repository, or one whose visibility is unknown, gets a link-only card: it is never fetched, rendered, counted or fed into the site digest, whatever the hub entry says and whatever the token can read. hub register writes a link-only entry for a private notes repository. Reuses the visibility reader of #296.

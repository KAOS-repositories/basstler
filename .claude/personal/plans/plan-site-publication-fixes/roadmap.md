# plan-site-publication-fixes — standing rules

- Each item is one bug pull request off main with a failing test first, labelled bug.
- Publication reports a problem before the user takes a step it would make useless.
- The build reads each listed repository's visibility from GitHub. A private repository, or one whose visibility is unknown, is never fetched, rendered, counted or fed into the site digest, and shows as skipped, whatever the token can read. Reuses #296's visibility reader, kept reusable by the service.

## Plan
- Tests first: dataset workspace with listed, transitively required, unrequired and stdlib imports
- Map each import to its distribution (`packages_distributions()`); stdlib is never third-party
- Allowed: own requirements + their closure (no extras) + allowed set of listed basstler distributions
- Report through `code-rules check` and the CI comparison with the base
- Update the package-boundary rule text; regenerate `AGENTS.md`

## Done
- Bootstrap: branch, draft PR #288, item recorded in progress

## Next
- Open question: count `build-system.requires` as requirements (basstler-build imports hatchling, packaging)?
- Baseline on `main`: hub imports pydantic, review-triage imports yaml; hold in the baseline or fix
- Write the failing tests

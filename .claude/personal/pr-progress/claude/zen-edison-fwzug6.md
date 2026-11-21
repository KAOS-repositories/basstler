## Plan
- Port the basstler.plan command lines to cyclopts (manifest_tools first), keeping every command, option and status.

## Done
- Merged main (5667d3e1) into the branch at 69a520e0: 8 real conflicts resolved (a shallow clone had shown 110); merge-probe CLEAN.
- Reapplied main's --origin-url, --saving and unmodelled-items onto the cyclopts manifest_tools; the origin refusal is PlanManifest.checkout_repository (review thread).
- ruff and the plan, code-rules and command-line tests pass. Remaining suite failures are the container's: libcst missing for the hook python, Playwright Chromium.
- PR description updated; both review threads answered, left open.

## Next
- Read CI at 69a520e0.
- Reviewer answers: what the `Parameter` annotations should look like (item_brief.py thread); whether PlanManifest is the right home.
- Item notes in plan.yaml still name --notes-remote-url: update to --origin-url.

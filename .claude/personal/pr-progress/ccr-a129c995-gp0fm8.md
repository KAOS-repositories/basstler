## Plan
- Agentic loop: kickoff -> review -> resolve -> review ..., opt-in, capped rounds (PR #315).

## Done
- `basstler.plan.agentic_loop` (settings, stages, Stop hook, cloud/local session start), `/plan-item-review`, `/plan-item-loop`, kickoff/resolve handover steps, tests; draft PR #315 labelled release:minor.

## Next
- Hardening items stack on this branch (blocking-findings-stop, loud-handover, github-loop-state, headless-session-limits, ci-gate); loop-end-to-end runs after them.
- Hub Playwright tests were not runnable in this container; CI decides them.

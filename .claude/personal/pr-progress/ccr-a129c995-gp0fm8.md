## Plan
- Agentic loop: kickoff -> review -> resolve -> review ..., opt-in, capped rounds (PR #315).

## Done
- `basstler.plan.agentic_loop` (settings, stages, Stop hook, cloud/local session start), `/plan-item-review`, `/plan-item-loop`, kickoff/resolve handover steps, tests; draft PR #315 labelled release:minor.

## Next
- Try one real loop end to end (local `claude --print` and a cloud session) and adjust the skill text from what it does.
- Hub Playwright tests were not runnable in this container; CI decides them.

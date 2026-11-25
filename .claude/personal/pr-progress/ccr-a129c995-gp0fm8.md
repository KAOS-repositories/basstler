## Plan
- Agentic loop: kickoff -> review -> resolve -> review ..., opt-in, capped rounds; every session marks the PRs it pushed viewed (PR #315).

## Done
- `basstler.plan.agentic_loop`, `/plan-item-review`, `/plan-item-loop`, kickoff/resolve handover steps, tests.
- Review-triage Stop hook marks every open PR at a local branch tip (one stamp entry per PR).

## Next
- Try one real loop end to end (local `claude --print` and a cloud session) and adjust the skill text from what it does.
- Hub Playwright tests were not runnable in this container; CI decides them.

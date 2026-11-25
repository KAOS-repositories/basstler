---
name: plan-item-loop
description: Turn the agentic loop on or off: a finished kickoff starts a review session, a review with findings starts a resolve session, and a resolve starts the next review, up to a number of rounds. Invoke as "/plan-item-loop {on|off} [rounds={n}]". Use when the user wants finished items reviewed and resolved by sessions of their own.
allowed-tools: Bash
---

# Plan item loop

Run commands as [`running-commands.md`](../running-commands.md) says, with
`${CLAUDE_PLUGIN_ROOT}` as the `${BASSTLER_PLUGIN_ROOT}` it and every linked document name.

Turns the [agentic loop](./agentic-loop.md) on or off for every later session. Read that
document if the user asks what the loop does rather than restating it here.

## 1. Work out what was asked for

- **On or off.** "Review and fix my items by themselves" is on; "stop starting sessions"
  is off. If the request does not settle it, ask with `AskUserQuestion`: the write
  persists.
- **The rounds**, only when the user named a number: the most reviews one pull request
  gets before the loop stops.

## 2. Set it

```bash
"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" plan.agentic_loop turn-on [--rounds <n>]
"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" plan.agentic_loop turn-off
```

Both push the setting to the personal-notes branch, then print it as JSON read back from
there. Report `enabled` and `maximum_review_rounds` from that output. Tell the user that
the setting follows them into every clone and session, and that one invocation of
`/plan-item-kickoff` or `/plan-item-resolve` can still say `loop=on` or `loop=off`.

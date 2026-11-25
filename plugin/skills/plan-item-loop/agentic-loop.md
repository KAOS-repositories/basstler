# The agentic loop

When the loop is on, every stage that finishes on an item's pull request starts the
session of the stage after it, so nobody has to:

1. a kickoff that pushed its implementation starts **review round 1**;
2. a review that posted findings starts their **resolve**, in the same round;
3. a resolve that pushed its fixes starts the **next review round**.

It ends when a review posts no finding, or when the resolve of the last round the
setting's `maximum_review_rounds` allows is pushed.

## Whether it is on

The user's setting decides (`/plan-item-loop on|off`, off unless set), and an
invocation's `loop=on` or `loop=off` overrides it for that run. A session the loop
started carries `loop=on` and its `round=<n>` in its first message, so the whole loop
keeps going once started.

A session the loop started is unattended: run it in `auto` mode, and never stop for a
question a person would have to answer. Record what would have needed one in the pull
request instead, for the user to read.

## Handing over at the end of a stage

Run exactly one of these as the stage's last command, once everything it pushes is
pushed, with `--loop` or `--no-loop` only when the invocation said `loop=on` or
`loop=off`:

```bash
# after a kickoff (no round) or a resolve of round <n>:
"${BASSTLER_PLUGIN_ROOT}/hooks/basstler.sh" plan.agentic_loop finish-changes \
  --pull-request <number> [--review-round <n>] [--loop|--no-loop]
# after a review of round <n> that posted <k> findings:
"${BASSTLER_PLUGIN_ROOT}/hooks/basstler.sh" plan.agentic_loop finish-review \
  --pull-request <number> --review-round <n> --findings <k> [--loop|--no-loop]
```

Run it from the checkout of the pull request's branch. It prints one JSON object:
`next_session` names the session that starts when this turn ends, and `loop_end` says why
none does (`turned_off`, `nothing_found` or `rounds_used_up`). Report which in one line.

When the turn ends, basstler's Stop hook starts the recorded session. On a computer it
runs `claude --print` in this checkout and appends what it prints to
`agentic-loop.log` in the repository's `basstler` state directory (under its common git
directory). In a cloud session the hook keeps the turn going instead and says which
`mcp__claude-code-remote__create_session` call to make: make exactly that call, then end
the turn.

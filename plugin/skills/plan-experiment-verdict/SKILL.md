---
name: plan-experiment-verdict
description: Carry out the owner's verdict on an experiment - accept and split it, keep iterating, or drop it. Invoke as "/plan-experiment-verdict {plan-id}/{item-id} {accept|iterate|drop}" followed by the owner's request. Use from the verdict buttons of a plan or goal page, or when the owner says how an experiment ends.
allowed-tools: Bash, Read, Edit, AskUserQuestion, Skill
---

# Plan Experiment Verdict

Run commands as [`running-commands.md`](../running-commands.md) says, with
`${CLAUDE_PLUGIN_ROOT}` as the `${BASSTLER_PLUGIN_ROOT}` it and every linked document name.

The owner decided how an experiment ends. This skill carries the decision out; it never
makes it. The item named by the first argument is the owner's verdict step
(`decision: experiment-verdict`): its `notes` say what the experiment is and what each
verdict involves for it. Read them first, together with everything the owner wrote after
the verdict word.

## 1. Read the verdict

The second argument is one of `accept`, `iterate` or `drop`. Anything else, or a missing
item, is a question for the owner (`AskUserQuestion`), never a guess.

## 2. Carry it out

- **accept**: split the experiment into the plan items it became, as stacked draft pull
  requests, one per item, then close the experiment's pull request. Use
  `/stacked-pr-maintenance` and `/plan-item-kickoff` for the stack.
- **iterate**: the owner's request says what to change. Make that change on the
  experiment's branch, push it, and leave the verdict step open. Without a request there is
  nothing to do: ask what to change.
- **drop**: close the experiment's pull request and delete its branch.

Do whatever else the verdict item's notes list for that verdict, and nothing they do not.

## 3. Record it

On `accept` and `drop`, once everything the notes list is done:

```bash
"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" __main__ goal mark-done <plan-id>/<item-id>
```

On `iterate` the step stays open: update the experiment item's `notes` to what is true now
and save the plan with `"${CLAUDE_PLUGIN_ROOT}/hooks/save-plan.sh"`.

## 4. Report

What was done for the verdict, what was left undone and why, and the plan site page of the
goal (`plan_site_page_url`).

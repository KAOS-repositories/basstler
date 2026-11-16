---
name: plan-goal
description: Set a goal - an outcome and the plan items that reach it - and show the ordered path to it, with the steps the owner performs. Invoke as "/plan-goal {the outcome, or a goal id}". Use when asked what it takes to reach an outcome, what to do next for one, or to track an outcome across plans.
allowed-tools: Bash, Read, AskUserQuestion, Skill
---

# Plan Goal

Run commands as [`running-commands.md`](../running-commands.md) says, with
`${CLAUDE_PLUGIN_ROOT}` as the `${BASSTLER_PLUGIN_ROOT}` it and every linked document name.

A goal stores only an id, a title and its target items. Everything else - which items are
needed, their order, what can start now, what waits on the owner - is computed from the
plans and live pull request state by the commands below. This skill makes the one judgment
a command cannot: which items the outcome the user described actually needs.

Every command here is run as

```bash
"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" __main__ goal <command> ...
```

from the project's checkout.

## 1. An existing goal, or a new one

`goal summary` prints one line per goal. When the argument is the id of one of them, skip
to step 4. Otherwise the argument is an outcome to turn into a goal.

## 2. Choose the targets

A target is an item whose completion *is* the outcome, never an item that only leads to
it: the path computes those from `depends_on`. Read the plans' items (titles and notes)
and pick the fewest items that, once done, make the outcome true.

- Word the title as a sentence that is true once the goal is reached.
- The id is short and kebab-case.
- When the outcome needs work no item covers, do not set the goal around the gap: run
  `/add-plan-item` for the missing work first, then return here.
- When two readings of the outcome give different targets, ask with `AskUserQuestion`,
  naming the items each reading would include.

## 3. Save it

```bash
"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" __main__ goal set <id> "<title>" --target <plan-id>/<item-id> [--target ...]
```

It refuses a target that names no item, and replaces a goal that already has the id.

## 4. Read the path and judge it

```bash
"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" __main__ goal path <id>
```

The path numbers the unfinished steps in the order recommended to carry them out, and says
whose move each is: a pull request under way is the owner's to review, unless its plan
records a blocker or its checks failed, which a session resolves first.

Read every step against the outcome, and against what the user said in this conversation:

- **A step the owner performs that no item records** (storing a secret, enabling a
  setting, merging in a given order): add it as an item with `performed_by: owner` and its
  `commands`, as [`plan-schema.md`](../plan-create/plan-schema.md)'s "Steps the owner
  performs" says.
- **A step that must wait for a merge, not only a pull request out of draft**: list the
  dependency under `depends_on_merged` ("Needing a dependency merged").
- **A step a further push to a draft would undo** (marking its files viewed): list the
  dependency under `depends_on_pushes_done` ("Needing a dependency's pushes done").
- **A step a command can prove done**: give it `done_when` ("Done checks"). A step with
  none is closed on the owner's word with `goal mark-done`.

Save plan edits with `"${CLAUDE_PLUGIN_ROOT}/hooks/save-plan.sh"`, then print the path
again.

## 5. Report

- The goal's page: `plan_site_page_url` gives the repository's page; the goal is listed
  there and has its own page under `_goals/<id>/`.
- The next move, from `goal next <id>`, then the whole numbered sequence with each step
  that waits on the owner and its commands, exactly as the path prints them.
- Every judgment made in steps 2 and 4, so the user can correct it.

## Later

- `goal check <id>` runs the pending done checks and records the steps that pass.
- `goal mark-done <plan-id>/<item-id>` records a step as done on the owner's word.
- The session-start summary's `goals:` line shows each goal's progress and next step.

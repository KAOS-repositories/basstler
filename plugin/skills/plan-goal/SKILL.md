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
source "${CLAUDE_PLUGIN_ROOT}/hooks/resolve-personal-notes-config.sh"
"${BASSTLER_PYTHON}" -m basstler goal <command> ...
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
"${BASSTLER_PYTHON}" -m basstler goal set <id> "<title>" --target <plan-id>/<item-id> [--target ...]
```

It refuses a target that names no item, and replaces a goal that already has the id.

## 4. Read the path and judge it

```bash
"${BASSTLER_PYTHON}" -m basstler goal path <id>
```

Read every step against the outcome, and against what the user said in this conversation:

- **A step the owner performs that no item records** (storing a secret, enabling a
  setting, merging in a given order): add it as an item with `performed_by: owner` and its
  `commands`, as [`plan-schema.md`](../plan-create/plan-schema.md)'s "Steps the owner
  performs" says.
- **A step that must wait for a merge, not only a pull request out of draft**: list the
  dependency under `depends_on_merged` ("Needing a dependency merged").
- **A step a command can prove done**: give it `done_when` ("Done checks"). A step with
  none is closed on the owner's word with `goal mark-done`.

Save plan edits with `"${CLAUDE_PLUGIN_ROOT}/hooks/save-plan.sh"`, then print the path
again.

## 5. Report

- The goal's page: `plan_site_page_url` gives the repository's page; the goal is listed
  there and has its own page under `_goals/<id>/`.
- The next step, from `goal next <id>`, and each step that waits on the owner with its
  commands, exactly as the path prints them.
- Every judgment made in steps 2 and 4, so the user can correct it.

## Later

- `goal check <id>` runs the pending done checks and records the steps that pass.
- `goal mark-done <plan-id>/<item-id>` records a step as done on the owner's word.
- The session-start summary's `goals:` line shows each goal's progress and next step.

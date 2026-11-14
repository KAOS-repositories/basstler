---
name: plan-recommend-models
description: Judge and set the recommended model (opus, sonnet or haiku) of plan items by task difficulty. Invoke as "/plan-recommend-models {plan-id} [{item-id}...]". Use when session start lists items without a recommended model, and from plan-create and add-plan-item when they add items.
allowed-tools: Bash, Read
---

# Plan Recommend Models

Run commands as [`running-commands.md`](../running-commands.md) says, with
`${CLAUDE_PLUGIN_ROOT}` as the `${BASSTLER_PLUGIN_ROOT}` it and every linked document name.

Gives plan items the `recommended_model` their difficulty calls for. The plan site
preselects it on the item's action buttons. Nothing is set without a judgement of the item.

## 1. Pick the items

- Named items: those the caller passed.
- Otherwise: the plan's items without a model.

```bash
"${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" plan.manifest_tools unmodelled-items <plan.yaml>
```

prints their ids comma-separated; empty output means there is nothing to do.

## 2. Judge each item

Read the item's `title`, `notes` and roadmap section, then choose by
[`plan-schema.md`](../plan-create/plan-schema.md)'s "Choosing the recommended model". Never
apply one model to every item, and never pick a default for the ones you could not judge:
read more of the item, or ask the user with `AskUserQuestion`.

## 3. Set it

- **An item the saved plan holds:**

  ```bash
  "${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" plan.item_bootstrap update \
      --plan <plan-id> --item <item-id> --recommended-model <alias>
  ```

- **An item not saved yet:** write `recommended_model: <alias>` into its `plan.yaml` entry
  and leave the save to the caller.
- **An item not drafted yet** (`/add-plan-item`): report the alias; the caller passes it
  as `--recommended-model` to `record`.

Report each item with its alias and the one-line reason.

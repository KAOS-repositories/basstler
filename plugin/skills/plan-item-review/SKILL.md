---
name: plan-item-review
description: Review a plan item's pull request: post its bugs and the repository's code-rule violations as inline review comments, for plan-item-resolve to address. Invoke as "/plan-item-review {pull-request-number}". Use when an agentic loop starts it, or when asked to review an item's pull request.
allowed-tools: Bash, Read, Grep, Glob, Skill, mcp__github__pull_request_read, mcp__github__pull_request_review_write, mcp__github__add_comment_to_pending_review, mcp__claude-code-remote__create_session
---

# Plan item review

Run commands as [`running-commands.md`](../running-commands.md) says, with
`${CLAUDE_PLUGIN_ROOT}` as the `${BASSTLER_PLUGIN_ROOT}` it and every linked document name.

Reviews one pull request and posts every finding on it as an inline review comment, where
`/plan-item-resolve` reads and addresses it. It changes no code. Invoked as
`/plan-item-review <pull-request-number> [round=<n>] [loop=on|off]`; `round` is 1 unless
given. When the [agentic loop](../plan-item-loop/agentic-loop.md) started this session,
work unattended, as that document says.

## 1. Check out the pull request

Read the pull request (`mcp__github__pull_request_read`, `method: "get"`) for its head
branch and base, and its review threads (`method: "get_review_comments"`): a finding an
unresolved thread already raises is not posted again. Work in the checkout of its head
branch, at the head commit GitHub reports:

```bash
git fetch origin <head branch> && git switch <head branch> && git merge --ff-only FETCH_HEAD
```

## 2. Find what is wrong

- **Bugs.** Run `/code-review medium <pull-request-number> --comment`. It posts its
  findings as inline comments itself; count the ones it posted.
- **The repository's code rules.** For the Python files the pull request changes
  (`git diff --name-only --diff-filter=d origin/<base>...HEAD -- '*.py'`), run:

  ```bash
  "${CLAUDE_PLUGIN_ROOT}/hooks/basstler.sh" __main__ code-rules check --all-lines <files>
  ```

  Keep only the violations on lines the pull request's diff adds or changes. Then read
  the diff against the rules in the repository's `AGENTS.md` (or `CLAUDE.md`), if it has
  one, for the rules no checker enforces, and keep each clear violation the diff adds.

## 3. Post the rule violations

Post every violation kept in step 2 in one review: create it pending
(`mcp__github__pull_request_review_write`, `method: "create"`), add one inline comment per
violation on its line (`mcp__github__add_comment_to_pending_review`) naming the rule and
the fix, and submit it with `method: "submit_pending"` and `event: "COMMENT"`. Never
approve or request changes. Skip this step when step 2 kept none.

## 4. Hand over

The findings are the comments `/code-review` posted plus those posted in step 3. Hand
over as [`agentic-loop.md`](../plan-item-loop/agentic-loop.md) says, with
`finish-review --review-round <round> --findings <findings>`, and end by reporting each
finding in one line with its `file:line`.

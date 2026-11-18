---
name: setup-review-triage
description: Set up marking a pull request's mechanical files viewed, from the user's own computer or from a repository's Actions, and walk the user through the steps only they can take. Invoke as "/setup-review-triage". Use when the user wants `basstler review-triage mark-viewed` to work, or when it failed.
allowed-tools: Bash, Read, AskUserQuestion
---

# Set up the review triage's marking of files viewed

Run commands as [`running-commands.md`](../running-commands.md) says, with
`${CLAUDE_PLUGIN_ROOT}` as the `${BASSTLER_PLUGIN_ROOT}` it and every linked document name.

`basstler review-triage mark-viewed` marks a pull request's mechanical files *Viewed*.
Only GitHub's GraphQL API sets that, for one account at a time, so it needs one of two
routes. The package's README, `docs/review-triage/README.md` in basstler's repository,
describes both; this skill sets them up.

**A denied command is a question, not a dead end.** Follow
[`session-rules.md`](../../hooks/session-rules.md): ask the user to accept it at once,
and run it when they do.

## 1. Ask which route

Read whether this is a cloud session:

```bash
source "${CLAUDE_PLUGIN_ROOT}/hooks/resolve-personal-notes-config.sh" && echo "${CLAUDE_CODE_REMOTE:-false}"
```

Ask with `AskUserQuestion`, one question, these options in this order:

- **Actions (Recommended)** - a workflow on a repository the user owns marks the files with their
  token when they ask, so any session can start it, a cloud one included.
- **My computer** - `gh` on the user's computer marks them when they ask; no stored
  token, but the computer has to be on.
- **Both** - set up both; `mark-viewed` tries the computer first and falls back to
  Actions.

## 2. My computer

In a local session, check the login:

```bash
gh auth status
```

- Logged in: say so, and that `mark-viewed` works here now. If it later reports that
  GitHub refused the mutation for lack of access, the fix is `gh auth refresh -s repo`.
- Not logged in, or `gh` missing: give the user the steps, each on its own line:
  install the GitHub CLI from https://cli.github.com, run `gh auth login` as the
  account the files are marked viewed for, then `gh auth status`. Never run
  `gh auth login` yourself: it opens an interactive prompt.

In a cloud session, nothing here can be checked. Tell the user the same steps, to take
in a terminal on their computer. Then tell them how to run
`basstler review-triage mark-viewed <number>` there: in a terminal, in a Claude Code
session on their computer, or in this session once their computer shares the checkout's
folder through Remote Control (the Claude desktop app: Settings, Claude Code, Remote
Control).

## 3. Actions

Run the setup. It proposes the workflow - on a fork, to the fork's parent from a fork
branch - turns on Actions, enables the workflow and checks for the token secret, then
prints what each step came to and what is left:

```bash
source "${CLAUDE_PLUGIN_ROOT}/hooks/resolve-personal-notes-config.sh" && ready_basstler_python && "${BASSTLER_PYTHON}" -m basstler review-triage set-up-mark-viewed --branch-or-tag "$(basstler_branch_or_tag)"
```

Relay its *Left to you* section as it printed it, with every link and command:
- **The token:** the form link fills in the token's name, owner and permissions. The
  user still selects the one repository the pull requests are opened on.
- **Storing it:** the user runs `gh secret set` on their computer, or uses the browser
  steps. Never ask for the token in the chat, and never pass it on a command line you
  run.
- **The workflow:** the setup opens a pull request adding it - on a fork, to the
  parent, followed by syncing the fork - or, where it may not push, links the new-file
  page with it filled in. Relay the link; the user, or the parent's maintainers,
  review and merge it.

**One token with the plan site:** when the user publishes a plan site whose repository
has the same owner as the pull requests' repository, offer one token for both instead.
Re-run `/setup-personal-notes`'s publication command with
`--mark-viewed-on <owner>/<name>`, naming the pull requests' repository. It then sets
this workflow up too and asks for one token, stored as both secrets with one command.
Relay its mark-viewed part as above. Where the owners differ, one fine-grained token
cannot do both, so each keeps its own.

**Every reviewer on a team:** when the user reviews pull requests on a repository that
other people also review, offer marking their own reviews from a repository they own.
Run the setup there with `--repository <owner>/<name>`, naming the team's repository,
and `--in-reviews-schedule <cron>`, proposing `"17 7-19 * * 1-5"` and saying each run
costs Actions minutes on that repository. With the plan site, the publication command
takes `--mark-viewed-in-reviews <cron>` beside `--mark-viewed-on` instead. Each other
reviewer runs the same on a repository of their own.

Once the user says they took the steps, run the setup again and report what it says
now, not what you expect. Call the route set up only when nothing is left.

## 4. Confirm

Say which routes work now and how to use them; a session's Stop hook marks its pull
request each turn by whichever route works. Otherwise:
- `basstler review-triage mark-viewed <number>` tries the computer route and falls back
  to Actions;
- `basstler review-triage request-mark-viewed <number>` asks Actions directly.

Say also that when both routes fail, the command's error says why each failed and links
the README.

## What this skill must never do

- **Never handle the token's value.** It goes from GitHub's form into the user's
  `gh secret set` prompt or the browser, never through the session.
- **Never push the workflow to a repository's default branch.** Neither you nor the
  setup writes one, a fork's included: a fork's default branch stays the same as its
  parent's, so the workflow reaches it only by merging upstream and syncing.
- **Never call a route set up from an unread or failed check.**

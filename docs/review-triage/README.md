# Review triage

`basstler review-triage` tells a pull request's *mechanical* files from those a reviewer
has to read: files that only follow a rename, a moved module or definition, reordered
imports, reformatting, or keyword arguments proven to bind the same parameters. It can
print that as a report and mark the mechanical files *Viewed* on GitHub, so the pull
request's file list shows only what needs reading.

```bash
basstler review-triage report <number>        # print the triage as Markdown
basstler review-triage mark-viewed <number>   # mark the mechanical files viewed, then print it
```

Run them in a checkout of the project. `--repository <owner>/<name>` names the pull
request's repository when it is not the checkout's `origin`.

## On every pull request, automatically

Most people want this: every pull request opened or updated on a repository has its
mechanical files marked viewed for you, with nothing to run. Updates matter, because
GitHub clears "Viewed" from a file that changes again. In a checkout of the repository
the pull requests are opened on, run:

```bash
basstler review-triage set-up-mark-viewed --on-every-pull-request
```

It installs a workflow there that runs on every pull request, and lists what is left to
you: the token, stored as that repository's `REVIEW_TRIAGE_VIEWER_TOKEN` secret, as in
[route 2](#route-2-from-a-repositorys-actions-from-anywhere). Run it again until nothing
is left.

- **Where it runs:** on the repository the pull requests are opened on, since a fork
  never sees its parent's pull request events. That needs a repository whose workflows
  and secrets you may change - one you maintain.
- **Whose files:** it marks them viewed for the token's owner, one account per
  repository. Everyone who can push to the repository can read its secrets through a
  workflow, so give the token the least it needs and an expiry.
- **Changing it:** the command never commits to a default branch. It opens a pull
  request adding the workflow from its own branch, `basstler/mark-viewed`, for you to
  review and merge. Where it may not push, it gives you GitHub's new-file page with the
  workflow already filled in.

The run uses `pull_request_target`, so pull requests from forks are marked too. It reads
their commits but runs none of their code.

## For every reviewer, from their own repository

The workflow above marks files for one account only, the token's owner. On a team, each
reviewer marks their own: a scheduled workflow in a repository *they* own, such as their
notes repository, holding their own token, marks every open pull request on the team's
repository that asks them for a review or that they reviewed. Each is marked from their
last review there, so after a push only what changed since they last looked stays to
read. In a checkout of their own repository, each reviewer runs:

```bash
basstler review-triage set-up-mark-viewed --repository <team-owner>/<name> \
    --in-reviews-schedule "17 7-19 * * 1-5"
```

The schedule is a cron expression in UTC; the one above runs hourly on weekday working
hours. Each run costs Actions minutes on the reviewer's repository, so pick one that
fits its budget. It lists the steps left as above. The token is created for the team
repository's owner, with *Pull requests: write* and *Contents: read*, and stored on the
reviewer's own repository, so no reviewer's token sits where others can reach it.

The same marking runs once, from your own computer, with:

```bash
basstler review-triage mark-viewed-in-reviews --repository <team-owner>/<name>
```

## Marking files viewed: pick a route

"Viewed" is kept for each GitHub account, and only GitHub's GraphQL API sets it.
`mark-viewed` tries the first route below. If that fails, or it runs in a Claude Code
cloud session, which cannot reach GraphQL, it falls back to the second. If both fail, it
stops with an error saying why each failed and pointing back here. Set up one route, or
both.

### Route 1: from your own computer

Marks the files with the credential `gh` is logged in with. It needs no stored token,
but your computer has to be on.

1. Install the GitHub CLI: <https://cli.github.com>.
2. Log in as the account the files are marked viewed for:

   ```bash
   gh auth login
   ```

   If `mark-viewed` says GitHub refused the mutation for lack of access, give the
   credential pull-request write access:

   ```bash
   gh auth refresh -s repo
   ```

3. Run `basstler review-triage mark-viewed <number>` in a terminal, or in a Claude Code
   session on your computer.

A Claude Code cloud session can use this route too, through a folder your computer
shares over Remote Control (the Claude desktop app: Settings, Claude Code, Remote
Control), once the session attaches it.

### Route 2: from a repository's Actions, from anywhere

A workflow on a repository you own marks the files with your token, stored as that
repository's `REVIEW_TRIAGE_VIEWER_TOKEN` secret. Any session can start it, a cloud
session included.

Set it up with:

```bash
basstler review-triage set-up-mark-viewed
```

It takes every step a command can:
- it proposes `.github/workflows/mark-viewed.yml`: on a fork, as a pull request to the
  fork's parent from the fork's `basstler/mark-viewed` branch, so the fork's default
  branch stays the same as its parent's; on any other repository, as a pull request to
  that repository;
- it turns on Actions and enables the workflow, which a fork starts with off;
- it checks whether the secret is stored.

It then lists the steps only you can take, with links that fill the forms in:

1. **Create the token:** a fine-grained token with *Pull requests: Read and write* and
   *Contents: Read* on the repository the pull requests are opened on. If that
   repository belongs to an organization you are not a member of, a fine-grained token
   cannot reach it; a classic token with the `repo` scope can, but reaches every
   repository you can.
2. **Store it** as the workflow repository's `REVIEW_TRIAGE_VIEWER_TOKEN` secret:

   ```bash
   gh secret set REVIEW_TRIAGE_VIEWER_TOKEN --repo <owner>/<fork>
   ```

   Keep it in your fork where you have one: everyone who can push to a repository can
   read its secrets through a workflow.
3. **Merge the pull request adding the workflow.** When an open pull request already
   carries the workflow, the command names it (the lowest one, for stacked pull
   requests) and opens nothing. Otherwise it opens one. Where GitHub refuses to open
   it, it links the pull request form with the title and description filled in. Where
   it may not even push the branch, it links GitHub's new-file page with the workflow
   filled in.
4. **Sync your fork** once the parent has merged it, so the fork's default branch
   carries the workflow too: `gh repo sync <owner>/<fork>`, or Sync fork on its page.
   Until then the fork's Actions cannot run it.

Where the secret cannot be read, as from a cloud session, the two token steps say to
skip them if it is stored already.

**One token for the plan site and this:** publishing the plan site with
`--mark-viewed-on <owner>/<name>` also sets this workflow up on the notes repository,
for that repository's pull requests. Where the plan site's repository and the pull
requests' repository have the same owner, it asks for one fine-grained token with both
jobs' permissions and stores it as both `PLAN_SITE_TOKEN` and
`REVIEW_TRIAGE_VIEWER_TOKEN`. A fine-grained token reaches one owner's repositories
only, so where the owners differ each job keeps a token of its own.

Run `set-up-mark-viewed` again afterwards: it checks every step and says when nothing
is left. `--workflow-repository` names another repository than the checkout's `origin`,
and `--repository` names the pull requests' repository when it is not the fork's parent.

From then on, `mark-viewed` falls back to the workflow on its own, and
`basstler review-triage request-mark-viewed <number>` asks the workflow directly. A run
refuses to start when the stored token belongs to another account than the one starting
it, so it never marks files viewed for someone else.

## In Claude Code

`/setup-review-triage` asks whether you want every pull request marked automatically,
or which route to mark them on demand, runs the setup above and walks you through the
steps left. `/setup-personal-notes` offers it as an optional step.

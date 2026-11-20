# Handing plans over

When someone else takes over a line of work, `basstler plan-handover` moves its plans to
them: from your personal-notes branch to theirs, by a pull request on their repository or
by a directory you send them.

## 1. Choose where they will work

The items' branches and pull requests stay where they are. The receiver either:

- **pushes to your repository**, as a collaborator with write access: they continue every
  item on its existing branch and pull request, and nothing about the plans changes; or
- **works in their own fork** of the same upstream: on import, each plan moves onto their
  fork, and every item whose pull request is still open on yours continues there. Its
  branch, and the branch its pull request stacks on where their fork lacks it, are
  pushed to their fork, its pull request is opened again there as a draft with the same
  title and base, linking the original, and the item names the new one. The original
  keeps its review threads and checks; the handover pull request's closing comment lists
  each original beside its continuation, so you can close yours. Items not started are
  opened on their fork, and the plans' tracking issues, which are numbers on your
  repository, are dropped. `--leave-underway-work` keeps the underway items on your pull
  requests instead.

## 2. Hand the plans over

From a checkout of the plans' repository, name every plan the work spans: a plan whose
items depend on a plan left out is refused.

**As a pull request** (recommended), opened as a draft on the receiver's repository -
theirs, or yours for a collaborator:

```bash
basstler plan-handover offer <plan-id> [<plan-id>...] --receiver-repository <owner>/<repository> [--receiver-login <login>] [--base <branch>]
```

It commits the handover under `plan-handover/` on top of the base branch (the
repository's default branch unless `--base` names another), pushes it to a
`basstler/plan-handover/...` branch of your `origin`, and opens the pull request,
mentioning `--receiver-login`. Its files are what the receiver reviews; it is never merged.
Offering the same plans again updates the pull request. With `--close-pull-requests`,
the open pull requests of the plans' underway items on your repository are closed, each
with a comment linking the handover pull request; the receiver's import continues them
all the same. Nothing is closed when the receiver pushes to your repository.

Every plan page on the plan site carries this command ready to copy: type the receiver's
GitHub login, or their repository as `owner/repository`, beside **Copy handover
command**. It names the plan and every plan it depends on, and a login stands for the
receiver's fork, named like the plan's repository.

**As a directory**, for a receiver without a repository you can open a pull request on:

```bash
basstler plan-handover export <plan-id> [<plan-id>...] --output <directory>
```

Either way the handover holds:

| Path | What it is |
| --- | --- |
| `HANDOVER.md` | Instructions for the receiver's coding agent: the rules and steps for working an item without basstler, and every item's state, branch, pull request, dependencies, notes and blockers. |
| `plans/<plan-id>/` | Each plan's `plan.yaml` and `roadmap.md`, as your notes branch holds them. |
| `pr-progress/<branch>.md` | The progress note of every handed-over item's branch that has one. |
| `repository-rules.yaml` | The rules every plan of the repository follows, if it has any. |

Items' `session` links are left out: only the person who ran a session can open it.

## 3. The receiver takes them on

**With basstler** (recommended): after its [setup](SETUP.md), from a checkout of the
repository the pull request is on:

```bash
basstler plan-handover import
```

It finds the handover pull request open there, saves each plan onto their notes branch after the plans it depends
on, so every save is validated as any other is, then their progress notes and rules, and
closes the pull request. When several are open it lists them and takes none over: name
one with `--pull-request <number>`, or take them all over, oldest first, with `--all`.
Running it again after a failure reuses the branches and pull
requests it already continued. Given a directory instead, `basstler plan-handover import
<directory>` reads it from there. It refuses a plan their notes branch already holds,
before saving anything. Items then start with `/plan-item-kickoff` and continue with
`/plan-item-resolve`, and the plans appear on their plan site.

**Without basstler:** point a coding agent at `HANDOVER.md` and an item. It is written
for the agent: the rules to read first and the steps that work the item from its branch,
pull request, progress note and the plan's standing rules.

## 4. Afterwards

Handing over leaves your notes branch as it was. Once the receiver has imported the
plans into their fork, delete your copies of the underway items' branches:

```bash
basstler plan-handover delete-branches <plan-id> [<plan-id>...] --receiver-repository <owner>/<repository>
```

It deletes the branch of every unmerged pull request of those items on your repository
whose commit the receiver's repository holds on a branch of the same name, closing the
pull request first if it is still open, and keeps the others, naming each. GitHub
cannot delete a pull request: closed, it stays listed with its review threads. Run it
before removing the plans, since it reads them from your notes branch.

Then remove the plans from your notes branch, or keep them to follow along: both of you
then see the same pull requests' live state. To remove them:

```bash
basstler plan-handover remove <plan-id> [<plan-id>...]
```

It removes the plans and their items' progress notes. A plan that another of your plans
depends on is refused, naming the items that depend on it, until those dependencies are
dropped or that plan is removed with it.

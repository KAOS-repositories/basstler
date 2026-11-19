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
basstler plan-handover offer <plan-id> [<plan-id>...] --to <owner>/<repository> [--receiver <login>] [--base <branch>]
```

It commits the handover under `plan-handover/` on top of the base branch (the
repository's default branch unless `--base` names another), pushes it to a
`basstler/plan-handover/...` branch of your `origin`, and opens the pull request,
mentioning `--receiver`. Its files are what the receiver reviews; it is never merged.
Offering the same plans again updates the pull request.

**As a directory**, for a receiver without a repository you can open a pull request on:

```bash
basstler plan-handover export <plan-id> [<plan-id>...] --output <directory>
```

Either way the handover holds:

| Path | What it is |
| --- | --- |
| `HANDOVER.md` | The guide: how to take the plans on with or without basstler, and every item's state, branch, pull request, dependencies, notes and blockers. |
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

It finds the handover pull request open there (name one with `--pull-request <number>`
when several are), saves each plan onto their notes branch after the plans it depends
on, so every save is validated as any other is, then their progress notes and rules, and
closes the pull request. Running it again after a failure reuses the branches and pull
requests it already continued. Given a directory instead, `basstler plan-handover import
<directory>` reads it from there. It refuses a plan their notes branch already holds,
before saving anything. Items then start with `/plan-item-kickoff` and continue with
`/plan-item-resolve`, and the plans appear on their plan site.

**Without basstler:** `HANDOVER.md` has a prompt to give Claude Code with any item's
section, which works the item from its branch, pull request, progress note and the plan's
standing rules.

## 4. Afterwards

Handing over leaves your notes branch as it was. Once the receiver has imported the
plans, remove them from yours, or keep them to follow along: both of you then see the
same pull requests' live state. A plan another of your plans depends on cannot be removed
until that dependency is dropped or the item it names is done.

# Handing plans over

When someone else takes over a line of work, `basstler plan-handover` moves its plans to
them: from your personal-notes branch, through a directory you give them, onto theirs.

## 1. Give them access to the work

The items' branches and pull requests stay where they are, so the receiver needs to push
to them: add them as a collaborator with write access to every repository the plans'
items are on. Nothing is migrated on GitHub, so pull request numbers, review threads,
stacked bases and tracking issues all stay valid.

## 2. Export the plans

From a checkout of the plans' repository:

```bash
basstler plan-handover export <plan-id> [<plan-id>...] --output <directory>
```

Name every plan the work spans: an export refuses a plan whose items depend on a plan it
leaves out. The directory holds:

| Path | What it is |
| --- | --- |
| `HANDOVER.md` | The guide: how to take the plans on with or without basstler, and every item's state, branch, pull request, dependencies, notes and blockers. |
| `plans/<plan-id>/` | Each plan's `plan.yaml` and `roadmap.md`, as your notes branch holds them. |
| `pr-progress/<branch>.md` | The progress note of every handed-over item's branch that has one. |
| `repository-rules.yaml` | The rules every plan of the repository follows, if it has any. |

Items' `session` links are left out: only the person who ran a session can open it.

Commit the directory somewhere the receiver can read it, such as a branch of the
repository, or send it to them.

## 3. The receiver takes them on

**With basstler** (recommended): after its [setup](SETUP.md), from a checkout of the
plans' repository:

```bash
basstler plan-handover import <directory>
```

That saves each plan onto their notes branch after the plans it depends on, so every
save is validated as any other is, then their progress notes and rules. It refuses a plan
their notes branch already holds, before saving anything. Items then start with
`/plan-item-kickoff` and continue with `/plan-item-resolve`, and the plans appear on
their plan site.

**Without basstler:** `HANDOVER.md` has a prompt to give Claude Code with any item's
section, which works the item from its branch, pull request, progress note and the plan's
standing rules.

## 4. Afterwards

The export leaves your notes branch as it was. Once the receiver has imported the plans,
remove them from yours, or keep them to follow along: both of you then see the same
pull requests' live state. A plan another of your plans depends on cannot be removed
until that dependency is dropped or the item it names is done.

# Review triage

`basstler review-triage` sorts a pull request's files into those a reviewer has to
read and those whose change is proven mechanical: imports, renames, formatting, a
move, or a code rule's fix. It reads the pull request from GitHub's REST API and its files from a git
checkout holding both ends; a checkout lacking them fetches them first.

## In another repository's CI

Copy [`examples/review-triage.yml`](examples/review-triage.yml) to
`.github/workflows/review-triage.yml`. Every pull request's run then carries the
report in its summary. The job needs only `contents: read` and
`pull-requests: read`.

## On your own machine

```bash
pip install "basstler @ git+https://github.com/KAOS-repositories/basstler@main"
basstler review-triage report <pull request> --repository <owner>/<name>
basstler review-triage mark-viewed <pull request> --repository <owner>/<name>
```

`mark-viewed` marks the mechanical files viewed for the account whose GitHub
credential is configured (`GH_TOKEN`, or `gh auth login`). It uses GitHub's GraphQL
API, which Claude Code cloud sessions cannot reach, so run it on your own machine.
Both commands default `--repository` to the checkout's `origin`.

By default both triage only what changed since your last submitted review of the pull
request, the head commit GitHub recorded for it, and the whole change when you have
not reviewed it. A credential GitHub names no account for, such as an Actions token,
has no review, so CI triages the whole change. The report's first line says where the
triage started. `--since <commit>`, `--last <count>` and `--from-merge-base` choose
another start.

A Python file counts as a rule's fix when recomputing the fixes of `basstler
code-rules fix` on its base reproduces its head, layout aside. Only the rules its base
breaks and its head no longer does are recomputed, and the report names each one, as
`read and write text as utf 8` for the rule on UTF-8 text.

A pre-commit hook is no place for it: a triage needs a pull request on GitHub.

### Samples left for review

A rename is proven to be applied consistently, not proven to be a good name. So for
each rename no file needing review already shows, `report` and `mark-viewed` leave one
mechanical file unviewed: the file defining the new name when it is mechanical,
otherwise the file using it most, reusing one file for several renames where they meet.
Moves get no sample. The report lists each sample with its rename. `--no-samples` leaves
none.

## Splitting the mechanical changes out

GitHub shows a file whose change is mostly mechanical, such as a definition moved into
a new file and edited there or a module of renames with one real change, as wholly
changed. To review only the rest:

```bash
basstler review-triage split-mechanical <pull request> --repository <owner>/<name>
```

It replaces the pull request's commits since your last review (the whole change if you
have not reviewed it; `--since`, `--last` and `--from-merge-base` as for `report`) with
two:

1. one making only the changes the triage proves mechanical: every mechanical file in
   its head version, definitions moved unchanged, and in every other file each
   statement whose change is mechanical, the rest keeping its earlier version with the
   pull request's renames applied;
2. one making every other change, whose tree is the former head's tree.

Before pushing, the triage must prove every file of the first commit mechanical, with
the pull request's own renames and moves; otherwise nothing is pushed. The second
commit's tree is the head's, so the pull request's files are the same as before. Both
commits are dated as the former head, so splitting the same pull request again gives
the same commits and pushes nothing new. The push is refused if the branch moved since
it was read, and the split is refused if the base branch was merged in after the commit
it starts from.

It then writes a *Mechanical changes* section into the description: the renames and
moves to check once, the files changed only mechanically, and a link to the second
commit, where the remaining changes are reviewed and commented on. Splitting again
replaces the section.

It rewrites the branch: run it as the author, or with permission to push to the
author's branch. The first commit is proven to change only mechanically, not to pass
the tests on its own.

## Declaring renames

The triage detects a rename from the diff. To declare one it missed, or reject one it
found, put a declaration comment in the pull request's description. The `declare`
command writes one:

```bash
basstler review-triage declare --rename old_name=new_name --rejected-rename other_name
```

`report` and `mark-viewed` take the same `--rename` and `--rejected-rename` options,
which outrank the description.

## Extending it

`PullRequestTriager` takes the rename sources and file judgments it applies:

- a `FileJudgment` decides the files it applies to; a `ContentComparison` is one for
  a set of file name suffixes;
- a `ChangeKind` subclass adds kinds of mechanical change;
- a `RenameSource` contributes renames or rejects ones an earlier source found;
- a `TriageOutput` publishes the outcome somewhere.

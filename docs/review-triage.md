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

By default both triage each file from where you last viewed it, by the viewed state
GitHub keeps for your account:

- a file you viewed as it is now is left out, neither judged nor marked again;
- a file you viewed before a later commit changed it is judged from the head it was
  viewed at, when a run saw it viewed there or marked it, else from the merge base;
- any other file is judged from the merge base.

Each run records the head commit the files are seen viewed or marked at on your
personal-notes branch, so every clone and session resumes from it, or, where no remote has that branch, in
the clone only; the run then says to set the branch up with `/setup-personal-notes`. Where GitHub's GraphQL API refuses the listing, as in a cloud session, the triage
starts from your last submitted review instead, and the whole change without one. A
credential GitHub names no account for, such as an Actions token, has viewed nothing,
so CI triages the whole change. The report's first line says where the triage started.
`--since <commit>`, `--last <count>` and `--from-merge-base` choose another start.

A Python file counts as a rule's fix when recomputing the fixes of `basstler
code-rules fix` on its base reproduces its head, layout aside. Only the rules its base
breaks and its head no longer does are recomputed, and the report names each one, as
`read and write text as utf 8` for the rule on UTF-8 text.

A pre-commit hook is no place for it: a triage needs a pull request on GitHub.

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

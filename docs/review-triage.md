# Review triage

`basstler review-triage` sorts a pull request's files into those a reviewer has to
read and those whose change is proven mechanical: imports, renames, formatting or a
move. It reads the pull request from GitHub's REST API and its files from a git
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

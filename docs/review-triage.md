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
curl -fsSL https://raw.githubusercontent.com/KAOS-repositories/basstler/main/scripts/review-triage.sh | bash -s -- <owner>/<name> <pull request number> --mark-viewed
```

The first run installs basstler into an environment of its own; it needs only git,
bash and either `uv` or Python 3.12+, and on Windows runs in Git Bash. Leave out
`--mark-viewed` to only print the triage, and the number to triage every open pull
request. To run an unmerged basstler branch, put its name in place of `main` in the
URL and set `BASSTLER_REF` to it. With basstler installed,
`basstler review-triage report` and `basstler review-triage mark-viewed` take the
pull request and `--repository <owner>/<name>`.

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

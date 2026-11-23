#!/usr/bin/env bash
# Triage a GitHub repository's open pull requests, or one of them, with basstler's review
# triage: which files a reviewer has to read, and which change only mechanically.
#
# Runs from any directory and needs only git, bash and either uv or Python 3.12+. The first
# run installs basstler into its own environment and keeps a clone of the repository to
# fetch the pull requests into; later runs reuse both.
#
# Usage:
#   review-triage.sh <pull request URL> [--mark-viewed] [--verbose] [-- <option>...]
#   review-triage.sh <owner>/<name> [<pull request number>] [--mark-viewed] [--verbose] [-- <option>...]
#
#   or, without downloading it first:
#   curl -fsSL https://raw.githubusercontent.com/KAOS-repositories/basstler/main/scripts/review-triage.sh \
#       | bash -s -- https://github.com/<owner>/<name>/pull/<number> --mark-viewed -- --from-merge-base
#
#   To run an unmerged basstler branch, put its name in place of main in the URL and
#   set BASSTLER_REF to it.
#
#   <pull request URL>     triage this pull request; <owner>/<name>#<number> works too
#   <pull request number>  triage only this pull request; every open one when left out
#   --mark-viewed          also mark the mechanical files viewed for your GitHub account;
#                          prints only how many files need review unless --verbose
#   --verbose              also print basstler's installation and, with --mark-viewed,
#                          the whole triage
#   -- <option>...         passed on to `basstler review-triage`, such as --from-merge-base,
#                          --since <commit>, --rename old=new or --ignore-rule <rule>
#
# The module-documentation rule is on unless `-- --ignore-rule module-documentation`
# turns it off.
#
# Environment:
#   GH_TOKEN or GITHUB_TOKEN  the GitHub credential; `gh auth token` when neither is set
#   BASSTLER_REF              the basstler branch, tag or commit to run (default: main)
#   BASSTLER_HOME             where the environment and clones are kept
#                             (default: ~/.cache/basstler-review-triage)
set -euo pipefail

readonly basstler_repository="https://github.com/KAOS-repositories/basstler"
readonly minimum_python="3.12"

fail() {
    printf 'review-triage: %s\n' "$1" >&2
    exit 1
}

usage() {
    printf 'usage: review-triage.sh <pull request URL> [--mark-viewed] [--verbose] [-- <option>...]\n' >&2
    printf '   or: review-triage.sh <owner>/<name> [<pull request number>] [--mark-viewed] [--verbose] [-- <option>...]\n' >&2
    exit 2
}

# %% arguments

repository=""
pull_request=""
command_name="report"
verbose=""
passed_on=()
while (($#)); do
    case "$1" in
    --mark-viewed) command_name="mark-viewed" ;;
    --verbose) verbose=1 ;;
    -h | --help) usage ;;
    --)
        shift
        passed_on=("$@")
        break
        ;;
    -*) fail "unknown option $1; options for basstler go after --" ;;
    *)
        if [[ -z "$repository" ]]; then
            repository="$1"
        elif [[ -z "$pull_request" ]]; then
            pull_request="$1"
        else
            fail "unexpected argument $1"
        fi
        ;;
    esac
    shift
done
if [[ -z "$pull_request" && (
    "$repository" =~ ^https?://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/([0-9]+)([/?#].*)?$ ||
    "$repository" =~ ^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([0-9]+)$ ) ]]; then
    repository="${BASH_REMATCH[1]}"
    pull_request="${BASH_REMATCH[2]}"
fi
[[ "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || usage
[[ -z "$pull_request" || "$pull_request" =~ ^[0-9]+$ ]] ||
    fail "the pull request must be a number, not $pull_request"
command -v git >/dev/null || fail "git is not installed"

home="${BASSTLER_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/basstler-review-triage}"
reference="${BASSTLER_REF:-main}"
environment="$home/environment"
clone="$home/repositories/$repository"

# %% basstler's environment

environment_python() {
    if [[ -x "$environment/bin/python" ]]; then
        printf '%s\n' "$environment/bin/python"
    else
        printf '%s\n' "$environment/Scripts/python.exe"
    fi
}

system_python() {
    local candidate
    for candidate in python3.13 python3.12 python3 python; do
        if command -v "$candidate" >/dev/null &&
            "$candidate" -c "import sys; sys.exit(sys.version_info < (${minimum_python/./, }))" 2>/dev/null; then
            printf '%s\n' "$candidate"
            return
        fi
    done
    fail "neither uv nor Python $minimum_python or later is installed"
}

install_basstler() {
    local commit stamp package python
    commit="$reference"
    if [[ ! "$reference" =~ ^[0-9a-f]{40}$ ]]; then
        commit="$(git ls-remote "$basstler_repository" "$reference" | head -n 1 | cut -f 1)"
        commit="${commit:-$reference}"
    fi
    stamp="$environment/.basstler-commit"
    if [[ -f "$stamp" && "$(cat "$stamp")" == "$commit" ]]; then
        return
    fi
    if [[ -n "$verbose" ]]; then
        printf 'review-triage: installing basstler %s (%s)\n' "$reference" "${commit:0:12}" >&2
    fi
    package="basstler @ git+$basstler_repository@$commit"
    mkdir -p "$home"
    if command -v uv >/dev/null; then
        [[ -d "$environment" ]] || uv venv --quiet --python ">=$minimum_python" "$environment"
        uv pip install --quiet --python "$(environment_python)" --reinstall-package basstler "$package"
    else
        python="$(system_python)"
        [[ -d "$environment" ]] || "$python" -m venv "$environment"
        "$(environment_python)" -m pip install --quiet --upgrade --force-reinstall --no-deps "$package"
        "$(environment_python)" -m pip install --quiet "$package"
    fi
    printf '%s\n' "$commit" >"$stamp"
}

# %% the repository's clone and pull requests

# basstler falls back to the clone's origin for the repositories it is not given.
prepare_clone() {
    local remote_url="https://github.com/$repository.git"
    if [[ ! -d "$clone/.git" ]]; then
        mkdir -p "$clone"
        git -C "$clone" init --quiet
    fi
    if git -C "$clone" remote get-url origin >/dev/null 2>&1; then
        git -C "$clone" remote set-url origin "$remote_url"
    else
        git -C "$clone" remote add origin "$remote_url"
    fi
}

open_pull_requests() {
    "$(environment_python)" - "$repository" <<'PYTHON'
import sys

from basstler.github.client import GitHubRestClient
from basstler.github.pull_request_changes import RestPullRequest
from basstler.github.repository import Repository

repository = Repository.parse(sys.argv[1])
pages = GitHubRestClient().get_pages(
    f"{repository.pull_requests_path}?state=open&per_page=100"
)
for page in pages:
    for payload in page:
        print(RestPullRequest.from_json(payload).number)
PYTHON
}

triage() {
    local output_options=()
    if [[ "$command_name" == "mark-viewed" && -z "$verbose" ]]; then
        output_options=(--summary-only)
    fi
    (cd "$clone" && "$(environment_python)" -m basstler review-triage "$command_name" "$1" \
        --repository "$repository" \
        ${output_options[@]+"${output_options[@]}"} ${passed_on[@]+"${passed_on[@]}"})
}

# %% running

install_basstler
prepare_clone
if [[ -n "$pull_request" ]]; then
    triage "$pull_request"
    exit
fi
numbers=()
while read -r number; do
    numbers+=("$number")
done < <(open_pull_requests | tr -d '\r')
if ((${#numbers[@]} == 0)); then
    printf 'review-triage: %s has no open pull request\n' "$repository" >&2
    exit
fi
failed=()
for number in "${numbers[@]}"; do
    printf '\n# %s#%s\n\n' "$repository" "$number"
    triage "$number" || failed+=("$number")
done
if ((${#failed[@]} > 0)); then
    fail "the triage failed for pull request(s) ${failed[*]}"
fi

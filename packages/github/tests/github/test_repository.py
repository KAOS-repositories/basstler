"""
Tests for github/repository.py: reading a GitHub repository out of a reference or a
remote URL.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from basstler.git.branch import Branch
from basstler.git.commands import GitCommandRunner
from basstler.github.repository import (
    NewTokenPage,
    GitHubAddress,
    MalformedRepositoryError,
    PullRequestReference,
    Repository,
    ReviewerInvolvement,
)

GITHUB_HOST = urlsplit(GitHubAddress.WEB).hostname
"""
The bare host an SSH remote names GitHub by.
"""

REPOSITORY = Repository("an-owner", "a-repository")
"""
The repository every well-formed reference and remote URL in these tests names.
"""

BRANCH = Branch(REPOSITORY, "main")
"""
The branch the page and path tests address.
"""

WORKFLOW = Path(".github/workflows/a-workflow.yml")
"""
The workflow the page and path tests address.
"""

# %% repository references


def test_repository_splits_a_reference_into_owner_and_name():
    assert Repository.parse(REPOSITORY.full_name) == REPOSITORY


def test_repository_round_trips_through_the_form_github_uses():
    assert str(Repository.parse(REPOSITORY.full_name)) == REPOSITORY.full_name


@pytest.mark.parametrize("malformed", ["no-separator", "/no-owner", "no-name/"])
def test_repository_rejects_a_reference_that_is_not_owner_and_name(malformed: str):
    """
    A half-parsed reference would silently target the wrong repository.
    """
    with pytest.raises(MalformedRepositoryError):
        Repository.parse(malformed)


@pytest.mark.parametrize(
    "url",
    [
        f"{GitHubAddress.WEB}/{REPOSITORY.full_name}.git",
        f"{GitHubAddress.WEB}/{REPOSITORY.full_name}",
        f"git@{GITHUB_HOST}:{REPOSITORY.full_name}.git",
        f"http://127.0.0.1:41729/git/{REPOSITORY.full_name}",
    ],
)
def test_repository_reads_the_owner_and_name_from_a_remote_url(url: str):
    """
    Every shape a fork remote takes names the same repository.

    A cloud session reaches GitHub through a local proxy, so the URL it sees shares
    neither host nor scheme with the one a laptop clone has.
    """
    assert Repository.from_remote_url(url) == REPOSITORY


@pytest.mark.parametrize("malformed", ["", f"{GitHubAddress.WEB}/only-one-segment"])
def test_repository_rejects_a_remote_url_naming_no_repository(malformed: str):
    """
    A remote URL naming no owner and name is refused.
    """
    with pytest.raises(MalformedRepositoryError):
        Repository.from_remote_url(malformed)


def test_a_named_repository_is_taken_as_named(tmp_path: Path):
    assert (
        Repository.from_name_or_remote(REPOSITORY.full_name, GitCommandRunner(tmp_path))
        == REPOSITORY
    )


def test_without_a_name_the_remote_s_repository_is_meant(tmp_path: Path):
    git = GitCommandRunner(tmp_path)
    git.run("init", "--quiet")
    git.run("remote", "add", "a-remote", REPOSITORY.clone_url)
    assert Repository.from_name_or_remote(None, git, "a-remote") == REPOSITORY


# %% clone roots


@pytest.mark.parametrize(
    "url",
    [
        f"git@{GITHUB_HOST}:{REPOSITORY.full_name}.git",
        REPOSITORY.clone_url_under(GitHubAddress.SSH),
    ],
)
def test_an_ssh_remote_s_repositories_are_reached_over_ssh(url: str):
    """
    Both ways git writes an SSH address keep other repositories on SSH.
    """
    assert GitHubAddress.clone_root_for(url) is GitHubAddress.SSH


@pytest.mark.parametrize(
    "url",
    [
        REPOSITORY.clone_url,
        f"http://127.0.0.1:41729/git/{REPOSITORY.full_name}",
    ],
)
def test_any_other_remote_s_repositories_are_reached_over_https(url: str):
    """
    A cloud session's local proxy keeps reaching other repositories over HTTPS.
    """
    assert GitHubAddress.clone_root_for(url) is GitHubAddress.WEB


# %% pages


def test_a_workflow_run_url_is_the_run_s_page_under_the_repository_s_actions():
    assert REPOSITORY.workflow_run_url(7) == f"{REPOSITORY.url}/actions/runs/7"


def test_the_settings_url_is_the_settings_page_under_the_repository():
    """
    The settings page is under the repository's page.
    """
    assert REPOSITORY.settings_url == f"{REPOSITORY.url}/settings"


def test_the_new_actions_secret_form_is_under_the_repository_s_settings():
    """
    The new Actions secret form is the repository's secrets settings page.
    """
    assert REPOSITORY.new_actions_secret_url == (
        f"{REPOSITORY.settings_url}/secrets/actions/new"
    )


def test_the_actions_settings_page_is_under_the_repository_s_settings():
    assert REPOSITORY.actions_settings_url == f"{REPOSITORY.settings_url}/actions"


def test_a_workflow_s_page_lists_its_runs_under_the_repository_s_actions():
    assert (
        REPOSITORY.workflow_page_url(WORKFLOW)
        == f"{REPOSITORY.url}/actions/workflows/{WORKFLOW.name}"
    )


def test_a_branch_is_moved_under_the_git_references_path():
    assert REPOSITORY.branch_update_path(BRANCH) == (
        f"{REPOSITORY.git_references_path}/heads/{BRANCH.name}"
    )


def test_a_file_s_page_is_under_its_branch():
    assert REPOSITORY.file_url(BRANCH, "a/b.md") == (
        f"{REPOSITORY.url}/blob/{BRANCH.name}/a/b.md"
    )


def test_the_compare_page_of_a_branch_on_the_same_repository_names_it_alone():
    assert REPOSITORY.compare_url(BRANCH, Branch(REPOSITORY, "topic")) == (
        f"{REPOSITORY.url}/compare/{BRANCH.name}...topic"
    )


def test_the_compare_page_of_a_branch_on_a_fork_names_its_owner():
    fork = Repository("a-forker", REPOSITORY.name)
    assert REPOSITORY.compare_url(BRANCH, Branch(fork, "topic")) == (
        f"{REPOSITORY.url}/compare/{BRANCH.name}...a-forker:topic"
    )


def test_a_token_form_is_under_github_s_web_root():
    assert NewTokenPage.FINE_GRAINED.url == (
        f"{GitHubAddress.WEB}/{NewTokenPage.FINE_GRAINED}"
    )


# %% branches of a repository


def test_a_branch_on_its_pull_request_s_repository_is_named_alone():
    branch = Branch(REPOSITORY, "topic")
    assert REPOSITORY.head_name(branch) == branch.name


def test_a_branch_on_a_fork_is_named_under_the_fork_s_owner():
    branch = Branch(Repository("a-forker", REPOSITORY.name), "topic")
    assert REPOSITORY.head_name(branch) == "a-forker:topic"


def test_a_branch_s_label_names_it_under_its_repository_s_owner():
    branch = Branch(Repository("a-forker", REPOSITORY.name), "topic")
    assert branch.repository.branch_label(branch) == "a-forker:topic"


# %% REST paths


def test_a_file_s_contents_path_reads_it_at_a_revision():
    assert REPOSITORY.contents_path("a/b.yml", "abc123") == (
        f"repos/{REPOSITORY.full_name}/contents/a/b.yml?ref=abc123"
    )


def test_a_file_s_contents_path_without_a_revision_writes_it():
    assert REPOSITORY.contents_path("a/b.yml") == (
        f"repos/{REPOSITORY.full_name}/contents/a/b.yml"
    )


def test_an_actions_secret_s_path_is_below_the_repository_s_secrets():
    assert REPOSITORY.actions_secret_path("A_SECRET") == (
        f"repos/{REPOSITORY.full_name}/actions/secrets/A_SECRET"
    )


def test_the_git_references_path_creates_references():
    assert REPOSITORY.git_references_path == f"repos/{REPOSITORY.full_name}/git/refs"


def test_a_branch_s_reference_path_is_below_the_git_reference_api():
    assert REPOSITORY.branch_reference_path(BRANCH) == (
        f"repos/{REPOSITORY.full_name}/git/ref/heads/{BRANCH.name}"
    )


def test_the_actions_permissions_path_is_below_the_repository_s_actions():
    assert REPOSITORY.actions_permissions_path == (
        f"repos/{REPOSITORY.full_name}/actions/permissions"
    )


def test_a_workflow_s_path_is_below_the_repository_s_workflows():
    assert REPOSITORY.workflow_resource_path(WORKFLOW) == (
        f"repos/{REPOSITORY.full_name}/actions/workflows/{WORKFLOW.name}"
    )


def test_a_workflow_s_dispatch_path_is_below_its_own_path():
    assert REPOSITORY.workflow_dispatch_path(WORKFLOW) == (
        f"{REPOSITORY.workflow_resource_path(WORKFLOW)}/dispatches"
    )


@pytest.mark.parametrize("involvement", list(ReviewerInvolvement))
def test_the_reviewer_s_pull_request_search_finds_open_ones_on_the_repository(
    involvement: ReviewerInvolvement,
):
    """
    The search asks for the repository's open pull requests the credential's account
    takes part in reviewing that way.
    """
    address = urlsplit(REPOSITORY.reviewer_pull_request_search_path(involvement))

    assert address.path == "search/issues"
    assert parse_qs(address.query)["q"] == [
        f"repo:{REPOSITORY.full_name} is:pr is:open {involvement}:@me"
    ]


def test_a_job_log_path_is_the_one_the_actions_api_serves_it_from():
    assert (
        REPOSITORY.job_log_path(7)
        == f"repos/{REPOSITORY.full_name}/actions/jobs/7/logs"
    )


# %% pull request references


def test_a_pull_request_s_api_url_is_the_one_the_pulls_api_serves_it_from():
    reference = PullRequestReference(REPOSITORY, 7)
    assert reference.api_url == (
        f"https://api.github.com/repos/{REPOSITORY.full_name}/pulls/7"
    )

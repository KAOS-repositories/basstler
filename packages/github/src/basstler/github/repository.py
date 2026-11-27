"""
A GitHub repository, identified the way GitHub itself writes it, and read out of the
references and git remote URLs the tooling is handed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode, urlsplit

from pydantic import Field

from basstler.git.branch import Branch
from basstler.git.commands import GitCommandRunner
from basstler.git.repository import GitRepository


class GitHubAddress(StrEnum):
    """
    The GitHub URLs this package builds addresses on or points the user to.
    """

    WEB = "https://github.com"
    """
    The root of every web URL and of every clone URL reached over HTTPS.
    """

    API = "https://api.github.com"
    """
    The root of every REST call.
    """

    SSH = "ssh://git@github.com"
    """
    The root of every clone URL reached over SSH.
    """

    STATUS = "https://www.githubstatus.com"
    """
    The page where GitHub reports its incidents.
    """

    @classmethod
    def clone_root_for(cls, remote_url: str) -> GitHubAddress:
        """
        :param remote_url: A git remote URL.
        :return: The root other repositories are reached under over the same transport:
            :attr:`SSH` for an SSH remote, :attr:`WEB` for any other.
        """
        before_path, colon, _ = remote_url.partition(":")
        is_short_ssh_form = (
            bool(colon) and "/" not in before_path and "@" in before_path
        )
        if is_short_ssh_form or urlsplit(remote_url).scheme == urlsplit(cls.SSH).scheme:
            return cls.SSH
        return cls.WEB


class NewTokenPage(StrEnum):
    """
    The signed-in account's forms creating a personal access token, below
    :attr:`GitHubAddress.WEB`.
    """

    FINE_GRAINED = "settings/personal-access-tokens/new"
    """
    The form creating a fine-grained token.
    """

    CLASSIC = "settings/tokens/new"
    """
    The form creating a classic token.
    """

    @property
    def url(self) -> str:
        """
        The form's address.
        """
        return f"{GitHubAddress.WEB}/{self}"


class ReviewerInvolvement(StrEnum):
    """
    How the credential's account takes part in reviewing a pull request, as the
    qualifier GitHub's issue search finds such pull requests by.
    """

    REVIEW_REQUESTED = "review-requested"
    """
    Its review is requested, from it or from a team it belongs to.
    """

    REVIEWED = "reviewed-by"
    """
    It has submitted a review, after which GitHub no longer lists the request.
    """


@dataclass
class MalformedRepositoryError(ValueError):
    """
    Raised when a repository reference is not in ``owner/name`` form.
    """

    text: str
    """
    The value that could not be parsed.
    """

    def __str__(self) -> str:
        """:return: What was expected and what arrived instead."""
        return f"expected a repository as 'owner/name', got {self.text!r}"


@dataclass(frozen=True)
class Repository(GitRepository):
    """
    A GitHub repository, identified the way GitHub itself writes it.
    """

    owner: str
    """
    The user or organization the repository belongs to.
    """

    name: str
    """
    The repository's own name.
    """

    @classmethod
    def parse(cls, text: str) -> Repository:
        """
        Parse an ``owner/name`` repository reference.

        :param text: The reference to parse.
        :return: The parsed repository.
        :raises MalformedRepositoryError: If *text* is not ``owner/name``.
        """
        if not cls.is_full_name(text):
            raise MalformedRepositoryError(text)
        owner, _, name = text.partition("/")
        return cls(owner, name)

    @classmethod
    def from_name_or_remote(
        cls, name: str | None, git: GitCommandRunner, remote: str = "origin"
    ) -> Repository:
        """
        :param name: A repository as ``owner/name``, or ``None``.
        :param git: The current checkout.
        :param remote: The remote whose repository is meant when no name is given.
        :return: The repository named, else the one *remote* points at.
        :raises MalformedRepositoryError: If *name* is not ``owner/name``.
        """
        if name:
            return cls.parse(name)
        return cls.from_remote_url(git.run("remote", "get-url", remote))

    @classmethod
    def from_configured_remote(
        cls, git: GitCommandRunner, remote: str = "origin"
    ) -> Repository:
        """
        :param git: A checkout.
        :param remote: One of its remotes.
        :return: The repository the URL the checkout configures for *remote* names, not
            git's rewrite of that URL.
        """
        return cls.from_remote_url(git.run("config", "--get", f"remote.{remote}.url"))

    @staticmethod
    def is_full_name(text: str) -> bool:
        """
        :param text: A value that may name a repository.
        :return: Whether *text* is an ``owner/name`` repository reference.
        """
        owner, separator, name = text.partition("/")
        return bool(owner and separator and name)

    @staticmethod
    def _remote_url_segments(url: str) -> list[str]:
        """
        Split a remote URL into its path segments, discarding scheme and host.

        :param url: The remote URL to split.
        :return: The path segments, which name a repository when there are two or more.
        """
        reference = url.removesuffix(".git").rstrip("/")
        if "://" in reference:
            _, _, host_and_path = reference.partition("://")
            _, _, path = host_and_path.partition("/")
        elif ":" in reference:
            _, _, path = reference.rpartition(":")
        else:
            return []
        return [segment for segment in path.split("/") if segment]

    @classmethod
    def names_a_repository(cls, url: str) -> bool:
        """
        Test whether a remote URL points at a repository at all.

        :param url: The remote URL to test.
        :return: Whether it names an ``owner/name`` pair.
        """
        return len(cls._remote_url_segments(url)) >= 2

    @classmethod
    def from_remote_url(cls, url: str) -> Repository:
        """
        Read the repository a git remote URL points at.

        Accepts every form a fork remote takes - HTTPS, SSH, and the local proxy a cloud
        session is given - by discarding the host and taking the last two path segments.

        :param url: The remote URL to read.
        :return: The repository it names.
        :raises MalformedRepositoryError: If *url* names no ``owner/name`` pair.
        """
        segments = cls._remote_url_segments(url)
        if len(segments) < 2:
            raise MalformedRepositoryError(url)
        return cls.parse("/".join(segments[-2:]))

    @property
    def full_name(self) -> str:
        """
        The ``owner/name`` form GitHub's own interface and the ``gh`` CLI use.
        """
        return f"{self.owner}/{self.name}"

    @property
    def url(self) -> str:
        """
        The repository's page on GitHub, which is also the base of every page within it.
        """
        return f"{GitHubAddress.WEB}/{self.full_name}"

    @property
    def clone_url(self) -> str:
        """
        The HTTPS URL git clones and fetches the repository from.
        """
        return self.clone_url_under()

    def clone_url_under(self, root: str = GitHubAddress.WEB) -> str:
        """
        :param root: Where repositories are kept as ``<root>/owner/name.git``: GitHub
            itself, or a directory of bare repositories standing in for it.
        :return: The URL git clones and fetches this repository from there.
        """
        return f"{root}/{self.full_name}.git"

    @property
    def settings_url(self) -> str:
        """
        The repository's settings page, where its visibility is changed.
        """
        return f"{self.url}/settings"

    def pull_request_url(self, number: int) -> str:
        """
        :param number: The pull request's number.
        :return: The pull request's page on GitHub.
        """
        return f"{self.url}/pull/{number}"

    def commit_url(self, commit: str) -> str:
        """
        :param commit: A commit of the repository.
        :return: The commit's page on GitHub, showing its change from its first parent.
        """
        return f"{self.url}/commit/{commit}"

    def issue_url(self, number: int) -> str:
        """
        :param number: The issue's number.
        :return: The issue's page on GitHub.
        """
        return f"{self.url}/issues/{number}"

    def workflow_run_url(self, run: int) -> str:
        """
        :param run: The Actions workflow run's own number.
        :return: The run's page on GitHub.
        """
        return f"{self.url}/actions/runs/{run}"

    @property
    def actions_settings_url(self) -> str:
        """
        The settings page that allows or forbids Actions in the repository.
        """
        return f"{self.settings_url}/actions"

    def workflow_page_url(self, workflow: Path) -> str:
        """
        :param workflow: The workflow's file in the repository.
        :return: The page listing the workflow's runs, where it is also enabled.
        """
        return f"{self.url}/actions/workflows/{workflow.name}"

    def file_url(self, branch: Branch, file_path: str) -> str:
        """
        :param branch: The branch holding the file.
        :param file_path: The file's path from the repository's root.
        :return: The file's page, rendered.
        """
        return f"{self.url}/blob/{branch.name}/{file_path}"

    def compare_url(self, base: Branch[Repository], head: Branch[Repository]) -> str:
        """
        :param base: A branch of this repository.
        :param head: A branch of this repository or of a fork of it.
        :return: The page comparing *head* with *base*.
        """
        return f"{self.url}/compare/{base.name}...{self.head_name(head)}"

    def head_name(self, head: Branch[Repository]) -> str:
        """
        :param head: A branch of this repository or of a fork of it.
        :return: The branch as a pull request opened on this repository names its
            head: its name on this repository, else its :meth:`branch_label`.
        """
        if head.repository == self:
            return head.name
        return head.repository.branch_label(head)

    def branch_label(self, branch: Branch[Repository]) -> str:
        """
        :param branch: A branch of this repository.
        :return: The ``owner:branch`` label naming it among the repository and its
            forks.
        """
        return f"{self.owner}:{branch.name}"

    @property
    def new_actions_secret_url(self) -> str:
        """
        The form on GitHub that adds an Actions secret to the repository.
        """
        return f"{self.settings_url}/secrets/actions/new"

    @property
    def api_path(self) -> str:
        """
        The repository's REST path, relative to :attr:`GitHubAddress.API`, which is also
        the base of every REST path within it and what ``gh api`` takes.
        """
        return f"repos/{self.full_name}"

    @property
    def issues_path(self) -> str:
        """
        The REST path of the repository's issues, which lists and opens them.
        """
        return f"{self.api_path}/issues"

    def issue_path(self, number: int) -> str:
        """
        :param number: The issue's number.
        :return: The REST path of that issue.
        """
        return f"{self.issues_path}/{number}"

    def issue_labels_path(self, number: int) -> str:
        """
        :param number: The issue's or pull request's number.
        :return: The REST path that sets that issue's labels.
        """
        return f"{self.issue_path(number)}/labels"

    def issue_comments_path(self, number: int) -> str:
        """
        :param number: The issue's number.
        :return: The REST path that lists and posts that issue's comments.
        """
        return f"{self.issue_path(number)}/comments"

    @property
    def labels_path(self) -> str:
        """
        The REST path of the labels defined on the repository, which lists and creates
        them.
        """
        return f"{self.api_path}/labels"

    @property
    def pull_requests_path(self) -> str:
        """
        The REST path of the repository's pull requests, which lists and opens them.
        """
        return f"{self.api_path}/pulls"

    def pull_request_path(self, number: int) -> str:
        """
        :param number: The pull request's number.
        :return: The REST path of that pull request.
        """
        return f"{self.pull_requests_path}/{number}"

    def pull_request_reviews_path(self, number: int) -> str:
        """
        :param number: The pull request's number.
        :return: The REST path listing that pull request's reviews, oldest first.
        """
        return f"{self.pull_request_path(number)}/reviews"

    def open_pull_requests_from_branch_path(self, branch: str) -> str:
        """
        :param branch: A branch of this repository itself.
        :return: The REST path listing the open pull requests opened from that branch.
        """
        query = urlencode({"head": f"{self.owner}:{branch}", "state": "open"}, safe=":")
        return f"{self.pull_requests_path}?{query}"

    def reviewer_pull_request_search_path(
        self, involvement: ReviewerInvolvement
    ) -> str:
        """
        :param involvement: How the credential's account takes part in the review.
        :return: The REST path of the issue search listing the repository's open pull
            requests the account takes part in reviewing that way.
        """
        query = f"repo:{self.full_name} is:pr is:open {involvement}:@me"
        return f"search/issues?{urlencode({'q': query})}"

    def compare_path(self, base: str) -> str:
        """
        :param base: What the head is compared with: a branch, or ``owner:branch`` for
            one in another repository of the same network.
        :return: The REST path of the comparison, which the head follows after ``...``.
        """
        return f"{self.api_path}/compare/{base}"

    def workflow_run_path(self, run: int) -> str:
        """
        :param run: The Actions workflow run's own number.
        :return: The REST path of that run.
        """
        return f"{self.api_path}/actions/runs/{run}"

    def job_log_path(self, job: int) -> str:
        """
        :param job: The Actions job's own number.
        :return: The REST path of that job's whole recorded log.
        """
        return f"{self.api_path}/actions/jobs/{job}/logs"

    def workflow_resource_path(self, workflow: Path) -> str:
        """
        :param workflow: The workflow's file in the repository.
        :return: The REST path of that workflow, which reads its state.
        """
        return f"{self.api_path}/actions/workflows/{workflow.name}"

    def workflow_dispatch_path(self, workflow: Path) -> str:
        """
        :param workflow: The workflow's file in the repository.
        :return: The REST path that starts a run of that workflow.
        """
        return f"{self.workflow_resource_path(workflow)}/dispatches"

    @property
    def actions_permissions_path(self) -> str:
        """
        The REST path of whether Actions may run in the repository.
        """
        return f"{self.api_path}/actions/permissions"

    def actions_secret_path(self, secret: str) -> str:
        """
        :param secret: The Actions secret's name.
        :return: The REST path of its metadata; GitHub never serves its value.
        """
        return f"{self.api_path}/actions/secrets/{secret}"

    def contents_path(self, file_path: str, revision: str | None = None) -> str:
        """
        :param file_path: The file's path from the repository's root.
        :param revision: The branch or commit to read it at, ``None`` to write it.
        :return: The REST path of the file's contents.
        """
        path = f"{self.api_path}/contents/{file_path}"
        return path if revision is None else f"{path}?ref={revision}"

    @property
    def git_references_path(self) -> str:
        """
        The REST path that creates git references, such as a new branch.
        """
        return f"{self.api_path}/git/refs"

    def branch_reference_path(self, branch: Branch) -> str:
        """
        :param branch: A branch of the repository.
        :return: The REST path of its git reference.
        """
        return f"{self.api_path}/git/ref/{branch.reference.removeprefix('refs/')}"

    def branch_update_path(self, branch: Branch) -> str:
        """
        :param branch: A branch of the repository.
        :return: The REST path that moves its git reference.
        """
        return f"{self.git_references_path}/{branch.reference.removeprefix('refs/')}"

    def git_requirement(self, distribution: str, reference: str) -> str:
        """
        A pip requirement installing a distribution straight from this repository.

        :param distribution: The distribution the repository builds.
        :param reference: The tag, branch or commit to install it at.
        :return: The requirement, as ``pip install`` takes it.
        """
        return f"{distribution} @ git+{self.url}@{reference}"

    def __str__(self) -> str:
        """:return: :attr:`full_name`."""
        return self.full_name


@dataclass(frozen=True)
class HasRepository:
    """
    Something that belongs to one GitHub repository.
    """

    repository: Annotated[Repository, Field(exclude=True)]
    """
    The repository it belongs to, which a payload written for it leaves out.
    """


@dataclass(frozen=True)
class PullRequestReference(HasRepository):
    """
    One pull request, named by the repository it is opened on and its number.

    Identity only: what a pull request currently *is* - open, merged, labelled - is read
    into a record of its own by whichever caller needs it.
    """

    number: int
    """
    The pull request's number.
    """

    @property
    def url(self) -> str:
        """
        The pull request's page on GitHub.
        """
        return self.repository.pull_request_url(self.number)

    @property
    def api_url(self) -> str:
        """
        The pull request's address in GitHub's REST pulls API.
        """
        return f"{GitHubAddress.API}/{self.repository.pull_request_path(self.number)}"

    @property
    def head_reference(self) -> str:
        """
        The ref the repository keeps the pull request's head commit under, whichever
        repository its branch is on.
        """
        return f"refs/pull/{self.number}/head"

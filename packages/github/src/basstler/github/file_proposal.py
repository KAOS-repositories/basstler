"""
Writing one file of a repository, directly or proposed for a default branch through a
pull request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

from basstler.class_property import classproperty
from basstler.git.branch import Branch
from basstler.github.client import (
    GitHubAttemptClient,
    GitHubCallFailed,
    GitHubResponse,
    HttpMethod,
    RepositoryWrite,
)
from basstler.github.git_objects import EncodedContent, GitObject
from basstler.github.pull_request import NewPullRequest
from basstler.github.pull_request_form import PullRequestForm
from basstler.github.wire_form import BranchFullReference, BranchName
from basstler.github.repository import Repository
from basstler.github.repository_access import PullRequestListState
from basstler.github.repository_resources import RepositoryRead, ResourceWrite
from basstler.github.rest_models import PullRequestPage, RestPullRequestSummary
from basstler.json_model import ValidatedJSONModel

# %% the contents API


class RepositoryFile(GitObject, EncodedContent):
    """
    One file of a repository, as the contents API returns it, standing for the blob it
    holds.
    """


@dataclass(frozen=True)
class FileRead(RepositoryRead[RepositoryFile]):
    """
    Reads one file of a repository at one revision.
    """

    file_path_from_repository_root: str
    """
    The file's path from the repository's root.
    """

    revision: str
    """
    The branch or commit to read it at.
    """

    @property
    def path(self) -> str:
        return self.repository.contents_path(
            self.file_path_from_repository_root, self.revision
        )


class FileWrite(ResourceWrite[RepositoryFile], EncodedContent):
    """
    Commits one file to a branch of a repository: creates it, or replaces the blob it
    holds.
    """

    file_path_from_repository_root: Annotated[str, Field(exclude=True)]
    """
    The file's path from the repository's root.
    """

    message: str
    """
    The commit's message.
    """

    branch: Annotated[Branch[Repository], BranchName()]
    """
    The branch the commit is made on.
    """

    replaced_object_hash: Annotated[
        str | None, Field(alias="sha", exclude_if=lambda value: value is None)
    ] = None
    """
    The blob the file holds now, which the API requires to replace it; ``None`` when
    the file is created.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.PUT

    @property
    def path(self) -> str:
        return self.repository.contents_path(self.file_path_from_repository_root)


@dataclass(frozen=True)
class FileCommit:
    """
    One file's whole content, committed to a branch of a repository.
    """

    branch: Branch[Repository]
    """
    The branch holding the file.
    """

    file_path_from_repository_root: str
    """
    The file's path from the repository's root.
    """

    text: str
    """
    The file's whole content.
    """

    message: str
    """
    The commit's message.
    """

    def read_at(self, revision: str) -> FileRead:
        """
        :param revision: The branch or commit to read the file at.
        :return: The read of the file there.
        """
        return FileRead(
            self.branch.repository, self.file_path_from_repository_root, revision
        )

    def write_replacing(self, current: RepositoryFile | None) -> FileWrite:
        """
        :param current: The file on :attr:`branch` now, ``None`` when there is none.
        :return: The write making the file hold :attr:`text`.
        """
        return FileWrite(
            repository=self.branch.repository,
            file_path_from_repository_root=self.file_path_from_repository_root,
            message=self.message,
            content=EncodedContent.encode(self.text),
            branch=self.branch,
            replaced_object_hash=None if current is None else current.object_hash,
        )


# %% branches and pull requests


class BranchReference(ValidatedJSONModel):
    """
    A git reference naming one branch, as the git references API reads and writes it.
    """

    branch: Annotated[Branch[Repository], Field(alias="ref"), BranchFullReference()]
    """
    The branch the reference names.
    """


class ExistingBranch(BranchReference):
    """
    A branch of a repository, as the git references API returns it.
    """

    target: Annotated[GitObject, Field(alias="object")]
    """
    The commit the branch points at.
    """


@dataclass(frozen=True)
class BranchReferenceRead(RepositoryRead[ExistingBranch]):
    """
    Reads where one branch of a repository points.
    """

    branch: Branch[Repository]
    """
    The branch.
    """

    @property
    def path(self) -> str:
        return self.repository.branch_reference_path(self.branch)


class NewBranch(RepositoryWrite, BranchReference):
    """
    A branch that does not exist yet, starting at one commit.
    """

    start_commit: Annotated[str, Field(alias="sha")]
    """
    The hash of the commit the branch starts at.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.POST

    @property
    def path(self) -> str:
        return self.repository.git_references_path


# %% proposing the file


@dataclass(frozen=True)
class ProposalOutcome:
    """
    What proposing a file came to.
    """

    pull_request: PullRequestPage | None = None
    """
    The pull request proposing the file, ``None`` when none could be opened.
    """

    opened_now: bool = False
    """
    Whether this proposal opened it, rather than finding it open.
    """

    failure: GitHubCallFailed | None = None
    """
    Why no pull request could be opened, ``None`` otherwise.
    """

    form_url: str = ""
    """
    GitHub's form opening the pull request with everything filled in, when the branch
    holds the file but the pull request could not be opened; empty otherwise.
    """

    merges_into: Branch[Repository] | None = None
    """
    The branch the pull request merges into, when it is another than the base; ``None``
    otherwise.
    """


@dataclass(frozen=True)
class FileProposal:
    """
    One file proposed for a repository's default branch: committed to a branch of its
    own, on that repository or on a fork of it, and opened as a pull request a reviewer
    merges.
    """

    commit: FileCommit
    """
    The file, committed to the branch that carries it; its message is the pull
    request's title.
    """

    base: Branch[Repository]
    """
    The default branch the file is proposed for, on the repository the pull request is
    opened on.
    """

    description: str
    """
    The pull request's description, in Markdown.
    """

    @property
    def opening(self) -> NewPullRequest:
        """
        The pull request proposing the file, titled with the commit's message and
        opened ready to merge.
        """
        return NewPullRequest(
            self.base,
            self.commit.branch,
            self.commit.message,
            self.description,
            draft=False,
        )

    @property
    def form(self) -> PullRequestForm:
        """
        The form opening :attr:`opening`, with its title and description filled in.
        """
        opening = self.opening
        return PullRequestForm(opening.base, opening.head, opening.title, opening.body)

    @property
    def open_pull_requests_path(self) -> str:
        """
        The REST path listing every open pull request on the base's repository.
        """
        return PullRequestListState.OPEN.path_on(self.base.repository)

    @property
    def open_from_branch_path(self) -> str:
        """
        The REST path listing the open pull requests from the commit's branch into
        :attr:`base`.
        """
        return PullRequestListState.OPEN.path_between(self.opening)

    def propose(self, client: GitHubAttemptClient) -> ProposalOutcome:
        """
        Find an open pull request carrying the file, else put the file on the commit's
        branch and open a pull request for it, unless one is open already.

        :param client: Reads and writes both repositories.
        :return: The pull request, or why none could be opened.
        """
        carrying = self._pull_request_carrying(client)
        if carrying is not None:
            merges_into = carrying.base
            return ProposalOutcome(
                carrying,
                merges_into=None if merges_into.name == self.base.name else merges_into,
            )
        from_branch = client.attempt_get(self.open_from_branch_path)
        failed = (
            from_branch if from_branch.failure is not None else None
        ) or self._put_on_branch(client)
        if failed is not None:
            return ProposalOutcome(failure=failed.failure)
        if from_branch.body:
            return ProposalOutcome(PullRequestPage.from_json(from_branch.body[0]))
        return self._open_pull_request(client)

    def _pull_request_carrying(
        self, client: GitHubAttemptClient
    ) -> RestPullRequestSummary | None:
        """
        :param client: Reads the repository.
        :return: The open pull request from another branch than the commit's whose
            head holds the file with this content and which is not stacked on another
            such pull request, ``None`` when none does or they cannot be read.
        """
        listed = client.attempt_get(self.open_pull_requests_path)
        if listed.failure is not None:
            return None
        carrying = [
            pull_request
            for pull_request in map(RestPullRequestSummary.from_json, listed.body)
            if pull_request.head.name != self.commit.branch.name
            and self._held_by(client, pull_request)
        ]
        heads = {pull_request.head.name for pull_request in carrying}
        lowest = [
            pull_request
            for pull_request in carrying
            if pull_request.base.name not in heads
        ]
        return lowest[0] if lowest else None

    def _held_by(
        self, client: GitHubAttemptClient, pull_request: RestPullRequestSummary
    ) -> bool:
        """
        :param client: Reads the repository.
        :param pull_request: An open pull request.
        :return: Whether its head holds the file with this content.
        """
        held = FileRead(
            self.base.repository,
            self.commit.file_path_from_repository_root,
            pull_request.head.commit,
        ).attempt(client)
        return held.resource is not None and held.resource.text == self.commit.text

    def _put_on_branch(self, client: GitHubAttemptClient) -> GitHubResponse | None:
        """
        Start the commit's branch when it does not exist, then commit the file to it.

        :param client: Reads and writes the repository carrying the branch.
        :return: The answer that failed, ``None`` once the branch holds the file.
        """
        return self._create_branch(client) or self._write_file(client)

    def _create_branch(self, client: GitHubAttemptClient) -> GitHubResponse | None:
        """
        Start the commit's branch at :attr:`base`'s head when it does not exist.

        :param client: Reads and writes the repository carrying the branch.
        :return: The answer that failed, ``None`` when the branch exists now.
        """
        carrier = self.commit.branch.repository
        existing = BranchReferenceRead(carrier, self.commit.branch).attempt(client)
        if existing.resource is not None:
            return None
        if not existing.response.is_not_found:
            return existing.response
        base = BranchReferenceRead(self.base.repository, self.base).attempt(client)
        if base.resource is None:
            return base.response
        created = client.attempt_send(
            NewBranch(
                repository=carrier,
                branch=self.commit.branch,
                start_commit=base.resource.target.object_hash,
            )
        )
        return created if created.failure is not None else None

    def _write_file(self, client: GitHubAttemptClient) -> GitHubResponse | None:
        """
        Commit the file to the commit's branch unless it holds this content already.

        :param client: Reads and writes the repository carrying the branch.
        :return: The answer that failed, ``None`` when the branch holds the file now.
        """
        existing = self.commit.read_at(self.commit.branch.name).attempt(client)
        if existing.resource is None and not existing.response.is_not_found:
            return existing.response
        if existing.resource is not None and existing.resource.text == self.commit.text:
            return None
        written = client.attempt_send(self.commit.write_replacing(existing.resource))
        return written if written.failure is not None else None

    def _open_pull_request(self, client: GitHubAttemptClient) -> ProposalOutcome:
        """
        :param client: Opens pull requests on the base's repository.
        :return: The pull request opened, or the form that opens it when GitHub
            refuses.
        """
        opened = client.attempt_send(self.opening)
        if opened.failure is not None:
            link = self.form.link
            return ProposalOutcome(
                failure=opened.failure,
                form_url="" if link is None else link.url,
            )
        return ProposalOutcome(PullRequestPage.from_json(opened.body), opened_now=True)

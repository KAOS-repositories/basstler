"""
Writing one file of a repository, directly or proposed for a default branch through a
pull request.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlencode

from pydantic import Field

from basstler.class_property import classproperty
from basstler.git.branch import Branch
from basstler.github.client import (
    GitHubAttemptClient,
    GitHubResponse,
    HttpMethod,
    RepositoryWrite,
)
from basstler.github.git_objects import EncodedContent, GitObject
from basstler.github.pull_request import NewPullRequest
from basstler.github.pull_request_form import PullRequestForm
from basstler.github.repository import Repository
from basstler.github.repository_access import (
    MAXIMUM_PULL_REQUESTS_PER_PAGE,
    ListingParameter,
    PullRequestListState,
)
from basstler.github.repository_resources import RepositoryRead, SettingWrite
from basstler.github.rest_models import PullRequestPage
from basstler.github.user_steps import AddFile, ReplaceFile, UserStep
from basstler.github.web_form import PrefilledForm, UrlQueryParameter
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


class FileWrite(SettingWrite[RepositoryFile], EncodedContent):
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

    branch: str
    """
    The name of the branch the commit is made on.
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

    @property
    def target(self) -> str:
        """
        The file and where it goes, as a phrase.
        """
        return (
            f"{self.file_path_from_repository_root} on "
            f"{self.repository.full_name}'s {self.branch}"
        )

    @property
    def manual_step(self) -> UserStep:
        branch = Branch(self.branch)
        if self.replaced_object_hash is None:
            return AddFile(
                self.target,
                NewFileForm(
                    self.repository,
                    branch,
                    self.file_path_from_repository_root,
                    self.text,
                ).url,
            )
        return ReplaceFile(
            self.target,
            self.repository.edit_file_url(branch, self.file_path_from_repository_root),
            self.text,
        )


class NewFileParameter(UrlQueryParameter):
    """
    The query parameters GitHub's new-file page fills its fields from.
    """

    FILE_NAME = "filename"
    """
    The file's path from the repository's root.
    """

    VALUE = "value"
    """
    The file's whole content.
    """


@dataclass(frozen=True)
class NewFileForm(PrefilledForm):
    """
    GitHub's page adding one file to a branch, with its path and content filled in.
    """

    repository: Repository
    """
    The repository the file is added to.
    """

    branch: Branch
    """
    The branch it is added to.
    """

    file_path_from_repository_root: str
    """
    The file's path from the repository's root.
    """

    text: str
    """
    The file's whole content.
    """

    @property
    def page_url(self) -> str:
        return self.repository.new_file_page_url(self.branch)

    @property
    def filled_fields(self) -> Mapping[UrlQueryParameter, str]:
        return {
            NewFileParameter.FILE_NAME: self.file_path_from_repository_root,
            NewFileParameter.VALUE: self.text,
        }


@dataclass(frozen=True)
class FileCommit:
    """
    One file's whole content, committed to a branch of a repository.
    """

    repository: Repository
    """
    The repository holding the branch.
    """

    branch: Branch
    """
    The branch the commit is made on.
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
        return FileRead(self.repository, self.file_path_from_repository_root, revision)

    def write_replacing(self, current: RepositoryFile | None) -> FileWrite:
        """
        :param current: The file on :attr:`branch` now, ``None`` when there is none.
        :return: The write making the file hold :attr:`text`.
        """
        return FileWrite(
            repository=self.repository,
            file_path_from_repository_root=self.file_path_from_repository_root,
            message=self.message,
            content=EncodedContent.encode(self.text),
            branch=self.branch.name,
            replaced_object_hash=None if current is None else current.object_hash,
        )


# %% branches and pull requests


class BranchReference(ValidatedJSONModel):
    """
    One branch, as the git references API returns it.
    """

    target: Annotated[GitObject, Field(alias="object")]
    """
    The commit the branch points at.
    """


@dataclass(frozen=True)
class BranchReferenceRead(RepositoryRead[BranchReference]):
    """
    Reads where one branch of a repository points.
    """

    branch: Branch
    """
    The branch.
    """

    @property
    def path(self) -> str:
        return self.repository.branch_reference_path(self.branch)


class NewBranch(RepositoryWrite, GitObject):
    """
    A branch that does not exist yet, starting at one commit, the object it stands for.
    """

    reference: Annotated[str, Field(alias="ref")]
    """
    The branch's full reference, as :attr:`Branch.reference` writes it.
    """

    @classproperty
    def method(cls) -> HttpMethod:
        return HttpMethod.POST

    @property
    def path(self) -> str:
        return self.repository.git_references_path


class PullRequestEnd(GitObject):
    """
    One end of a pull request - the branch it is opened from or merges into - standing
    for the commit the branch points at.
    """

    branch_name: Annotated[str, Field(alias="ref")]
    """
    The branch's name.
    """


class ListedPullRequest(PullRequestPage):
    """
    An open pull request, as the repository's listing of them gives it.
    """

    head: PullRequestEnd
    """
    The branch it is opened from.
    """

    base: PullRequestEnd
    """
    The branch it merges into.
    """


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

    failure: str = ""
    """
    Why no pull request could be opened, empty otherwise.
    """

    form_url: str = ""
    """
    GitHub's form opening the pull request with everything filled in, when the branch
    holds the file but the pull request could not be opened; empty otherwise.
    """

    merges_into: str = ""
    """
    The branch the pull request merges into, when it is another than the base; empty
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

    base_repository: Repository
    """
    The repository the pull request is opened on.
    """

    base: Branch
    """
    The default branch the file is proposed for.
    """

    description: str
    """
    The pull request's description, in Markdown.
    """

    @property
    def head_owner(self) -> str | None:
        """
        The owner of the fork carrying the file, ``None`` when it is on
        :attr:`base_repository` itself.
        """
        if self.commit.repository == self.base_repository:
            return None
        return self.commit.repository.owner

    @property
    def form(self) -> PullRequestForm:
        """
        The pull request form, with its title and description filled in.
        """
        return PullRequestForm(
            self.base_repository,
            self.base,
            self.commit.branch,
            self.commit.message,
            self.description,
            self.head_owner,
        )

    def propose(self, client: GitHubAttemptClient) -> ProposalOutcome:
        """
        Find an open pull request carrying the file, else put the file on the commit's
        branch and open a pull request for it, unless one is open already.

        :param client: Reads and writes both repositories.
        :return: The pull request, or why none could be opened.
        """
        carrying = self._pull_request_carrying(client)
        if carrying is not None:
            merges_into = carrying.base.branch_name
            return ProposalOutcome(
                carrying,
                merges_into="" if merges_into == self.base.name else merges_into,
            )
        from_branch = client.attempt_get(self.open_from_branch_path)
        failed = (
            from_branch if from_branch.failure is not None else None
        ) or self._put_on_branch(client)
        if failed is not None:
            return ProposalOutcome(failure=failed.failure.error_message())
        if from_branch.body:
            return ProposalOutcome(PullRequestPage.from_json(from_branch.body[0]))
        return self._open_pull_request(client)

    @property
    def open_pull_requests_path(self) -> str:
        """
        The REST path listing every open pull request on :attr:`base_repository`.
        """
        return self._listing_path({})

    @property
    def open_from_branch_path(self) -> str:
        """
        The REST path listing the open pull requests opened from the commit's branch.
        """
        return self._listing_path(
            {
                ListingParameter.HEAD: (
                    f"{self.commit.repository.owner}:{self.commit.branch.name}"
                )
            }
        )

    def _listing_path(self, filters: Mapping[ListingParameter, str]) -> str:
        """
        :param filters: Further filters of the listing.
        :return: The REST path listing :attr:`base_repository`'s open pull requests.
        """
        query = urlencode(
            {
                ListingParameter.STATE: PullRequestListState.OPEN.query,
                ListingParameter.PAGE_SIZE: MAXIMUM_PULL_REQUESTS_PER_PAGE,
                **filters,
            },
            safe=":",
        )
        return f"{self.base_repository.pull_requests_path}?{query}"

    def _pull_request_carrying(
        self, client: GitHubAttemptClient
    ) -> ListedPullRequest | None:
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
            for pull_request in map(ListedPullRequest.from_json, listed.body)
            if pull_request.head.branch_name != self.commit.branch.name
            and self._held_by(client, pull_request)
        ]
        heads = {pull_request.head.branch_name for pull_request in carrying}
        lowest = [
            pull_request
            for pull_request in carrying
            if pull_request.base.branch_name not in heads
        ]
        return lowest[0] if lowest else None

    def _held_by(
        self, client: GitHubAttemptClient, pull_request: ListedPullRequest
    ) -> bool:
        """
        :param client: Reads the repository.
        :param pull_request: An open pull request.
        :return: Whether its head holds the file with this content.
        """
        held = FileRead(
            self.base_repository,
            self.commit.file_path_from_repository_root,
            pull_request.head.object_hash,
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
        carrier = self.commit.repository
        existing = BranchReferenceRead(carrier, self.commit.branch).attempt(client)
        if existing.resource is not None:
            return None
        if not existing.response.is_not_found:
            return existing.response
        base = BranchReferenceRead(self.base_repository, self.base).attempt(client)
        if base.resource is None:
            return base.response
        created = client.attempt_send(
            NewBranch(
                repository=carrier,
                object_hash=base.resource.target.object_hash,
                reference=self.commit.branch.reference,
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
        :param client: Opens pull requests on :attr:`base_repository`.
        :return: The pull request opened, or the form that opens it when GitHub
            refuses.
        """
        head = self.commit.branch.name
        opened = client.attempt_send(
            NewPullRequest(
                self.base_repository,
                title=self.commit.message,
                head=head if self.head_owner is None else f"{self.head_owner}:{head}",
                base=self.base.name,
                body=self.description,
                draft=False,
            )
        )
        if opened.failure is not None:
            link = self.form.link
            return ProposalOutcome(
                failure=opened.failure.error_message(),
                form_url="" if link is None else link.url,
            )
        return ProposalOutcome(PullRequestPage.from_json(opened.body), opened_now=True)

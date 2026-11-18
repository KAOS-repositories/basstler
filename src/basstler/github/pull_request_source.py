"""
Where the live state of the pull requests a plan references is read from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

from basstler.github.client import (
    GitHubFullClient,
    GitHubResponse,
    GitHubRestClient,
)
from basstler.github.comparison import Comparison
from basstler.github.constants import MergeableState
from basstler.github.exceptions import GitHubRequestFailed
from basstler.github.pull_request_record import (
    PullRequestField,
    PullRequestHead,
)
from basstler.github.pull_request_state import (
    ForkLineage,
    LivePullRequests,
    PullRequestRecord,
    PullRequestState,
)
from basstler.github.repository import PullRequestReference, Repository
from basstler.github.repository_details import RepositoryDetails
from basstler.github.repository_access import GitHubRepository
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which reports a repository that cannot be read.
"""

READ_ACCESS_STATUSES = frozenset({HTTPStatus.NOT_FOUND, HTTPStatus.FORBIDDEN})
"""
What GitHub answers a token that is not granted a repository.
"""

# %% live pull request state


class PullRequestSource(ABC):
    """
    Where the live state of the pull requests a plan references comes from.
    """

    @abstractmethod
    def pull_request(self, reference: PullRequestReference) -> PullRequestRecord | None:
        """
        :param reference: The pull request to look up.
        :return: Its live state, or ``None`` if the repository has no such pull request.
        """

    @abstractmethod
    def issue_url(self, repository: Repository, number: int) -> str | None:
        """
        :param repository: The repository the issue or pull request is opened on.
        :param number: Its number.
        :return: Its web page, or ``None`` if the repository has no such number.
        """

    def read_failure_of(self, repository: Repository) -> GitHubRequestFailed | None:
        """
        :param repository: A repository a plan's items name.
        :return: The refusal of the token's access to it, or ``None`` if it can be read;
            ``None`` unless the source finds otherwise.
        """
        return None

    def fork_lineage_of(self, repository: Repository) -> ForkLineage | None:
        """
        :param repository: A repository that can be read.
        :return: What it was forked from, or ``None`` if it is not a fork, or the source
            cannot tell.
        """
        return None

    def upstream_pull_requests_of(
        self, fork: Repository, lineage: ForkLineage
    ) -> dict[str, int]:
        """
        :param fork: A repository that can be read and is a fork.
        :param lineage: What it was forked from.
        :return: The number of the open upstream pull request opened from each of its
            branches; none when the source cannot tell.
        """
        return {}

    def live_pull_requests_of(
        self, references: Iterable[PullRequestReference]
    ) -> LivePullRequests:
        """
        :param references: The pull requests to read.
        :return: The live state of each of them, and why each repository that cannot be
            read cannot be; a number the repository does not have is left out.
        """
        live_pull_requests = LivePullRequests()
        for reference in references:
            failure = self.read_failure_of(reference.repository)
            if failure is not None:
                live_pull_requests.read_failures[reference.repository] = failure
                continue
            repository = str(reference.repository)
            lineage = self.fork_lineage_of(reference.repository)
            if (
                lineage is not None
                and repository not in live_pull_requests.fork_lineages
            ):
                live_pull_requests.fork_lineages[repository] = lineage
                live_pull_requests.upstream_pull_requests[repository] = (
                    self.upstream_pull_requests_of(reference.repository, lineage)
                )
            record = self.pull_request(reference)
            if record is not None:
                live_pull_requests.pull_requests_by_repository.setdefault(
                    str(reference.repository), {}
                )[str(reference.number)] = record
        return live_pull_requests


@dataclass
class GitHubPullRequestSource(PullRequestSource):
    """
    Pull request state read from the GitHub REST API, once per repository.

    A repository's pull requests are listed in bulk on first use and kept, so a site
    covering many plans costs a handful of requests rather than one per item. A number
    the listing missed is read on its own. A repository whose details cannot be read is
    not listed.
    """

    client: GitHubFullClient
    """
    How the requests reach GitHub.
    """

    repository_details: dict[Repository, GitHubResponse] = field(default_factory=dict)
    """
    The answer to the read of each repository's details asked about so far.
    """

    listed_repositories: set[Repository] = field(default_factory=set)
    """
    Every repository whose pull requests have been listed into :attr:`pull_requests`.
    """

    pull_requests: dict[PullRequestReference, PullRequestRecord] = field(
        default_factory=dict
    )
    """
    Every pull request read so far, listed or read on its own.
    """

    reads_check_states: bool = True
    """
    Whether the check state of an open pull request is read; off, it stays unknown.
    """

    reads_mergeable_states: bool = False
    """
    Whether the mergeable state of an open pull request out of draft is read, which
    takes a request of its own; off, it stays unknown.
    """

    @classmethod
    def from_environment(
        cls, reads_check_states: bool = True, reads_mergeable_states: bool = False
    ) -> GitHubPullRequestSource:
        """
        :param reads_check_states: Whether open pull requests' check states are read.
        :param reads_mergeable_states: Whether open pull requests' mergeable states are
            read.
        :return: A source authenticating with whichever credential the environment
            carries.
        """
        return cls(
            client=GitHubRestClient(),
            reads_check_states=reads_check_states,
            reads_mergeable_states=reads_mergeable_states,
        )

    def client_for(self, repository: Repository) -> GitHubRepository:
        """
        :param repository: The repository to call.
        :return: A client for it.
        """
        return GitHubRepository(repository, self.client)

    def read_failure_of(self, repository: Repository) -> GitHubRequestFailed | None:
        """
        See :meth:`PullRequestSource.read_failure_of`: the refusal of the repository's
        details, asked once and reported when refused.

        :raises GitHubCallFailed: If the read fails other than by a refused access.
        """
        if repository in self.repository_details:
            return self.repository_details[repository].failure
        details = self.client.attempt_get(f"/{repository.api_path}")
        failure = details.failure
        if failure is not None and not (
            isinstance(failure, GitHubRequestFailed)
            and failure.status in READ_ACCESS_STATUSES
        ):
            raise failure
        self.repository_details[repository] = details
        if failure is not None:
            logger.warning(
                f"cannot read {repository}, so its pull requests are left out: "
                f"{failure.error_message()}"
            )
        return failure

    def fork_lineage_of(self, repository: Repository) -> ForkLineage | None:
        if self.read_failure_of(repository) is not None:
            return None
        return RepositoryDetails.from_json(
            self.repository_details[repository].body
        ).lineage

    def upstream_pull_requests_of(
        self, fork: Repository, lineage: ForkLineage
    ) -> dict[str, int]:
        return PullRequestHead.numbers_by_branch(
            self.client_for(lineage.upstream_repository).open_pull_requests(),
            fork.full_name,
        )

    def pull_request(self, reference: PullRequestReference) -> PullRequestRecord | None:
        record = self.listed_or_read(reference)
        if record is None:
            return None
        if self.reads_check_states and record.has_unread_checks:
            record.check_state = self.client_for(reference.repository).check_state(
                record.head_commit
            )
        if self.reads_mergeable_states and record.has_unread_mergeable_state:
            record.mergeable_state = self.mergeable_state(reference)
        if record.landed_upstream is None:
            record.landed_upstream = self.landed_upstream(reference.repository, record)
        return record

    def mergeable_state(self, reference: PullRequestReference) -> MergeableState | None:
        """
        :param reference: An open pull request.
        :return: What reading it on its own says about its conflicts - a listing leaves
            that out - or ``None`` when it cannot be read or GitHub reports none.
        """
        api_record = self.read_if_present(
            f"/{reference.repository.pull_request_path(reference.number)}"
        )
        if api_record is None:
            return None
        return PullRequestRecord.from_api(api_record).mergeable_state

    def landed_upstream(
        self, repository: Repository, record: PullRequestRecord
    ) -> bool | None:
        """
        Ask GitHub whether an open pull request's work is already in the upstream.

        :param repository: The repository the pull request is opened on.
        :param record: The pull request.
        :return: Whether every commit of its head is in the upstream's default branch
            and it has a commit beyond its own base, which a branch with nothing of its
            own does not; ``None`` when that is not asked of it, or GitHub cannot say.
        """
        lineage = self.fork_lineage_of(repository)
        if (
            lineage is None
            or record.state is not PullRequestState.OPEN
            or record.head_commit is None
            or record.base is None
        ):
            return None
        in_upstream = self.comparison(
            repository,
            f"{lineage.upstream_repository.owner}:{lineage.upstream_default_branch}",
            record.head_commit,
        )
        if in_upstream is None:
            return None
        if not in_upstream.head_is_contained_in_base:
            return False
        beyond_base = self.comparison(repository, record.base, record.head_commit)
        if beyond_base is None:
            return None
        return beyond_base.ahead_by > 0

    def comparison(
        self, repository: Repository, base: str, head: str
    ) -> Comparison | None:
        """
        :param repository: The repository holding the head.
        :param base: What the head is compared with.
        :param head: The commit compared.
        :return: GitHub's comparison, ``None`` when it cannot be read, which is
            reported.
        """
        path = f"/{repository.compare_path(base)}...{head}"
        answer = self.client.attempt_get(path)
        if answer.failure is not None:
            logger.warning(
                f"cannot compare {head} with {base} in {repository} ({path}), so it "
                f"is not known whether its pull request has landed: "
                f"{answer.failure.error_message()}"
            )
            return None
        return Comparison.from_json(answer.body)

    def listed_or_read(
        self, reference: PullRequestReference
    ) -> PullRequestRecord | None:
        """
        :param reference: The pull request to look up.
        :return: Its state as its repository's listing gave it, read on its own when the
            listing missed it, or ``None`` if the repository has no such pull request or
            cannot be read.
        """
        if self.read_failure_of(reference.repository) is not None:
            return None
        self.list_pull_requests_of(reference.repository)
        if reference not in self.pull_requests:
            api_record = self.read_if_present(
                f"/{reference.repository.pull_request_path(reference.number)}"
            )
            if api_record is None:
                return None
            self.pull_requests[reference] = PullRequestRecord.from_api(api_record)
        return self.pull_requests[reference]

    def issue_url(self, repository: Repository, number: int) -> str | None:
        """
        See :meth:`PullRequestSource.issue_url`; ``None`` also when the repository
        cannot be read.
        """
        if self.read_failure_of(repository) is not None:
            return None
        api_record = self.read_if_present(f"/{repository.issue_path(number)}")
        if api_record is None:
            return None
        return PullRequestField.HTML_URL.read(api_record, number)

    def list_pull_requests_of(self, repository: Repository) -> None:
        """
        Read every pull request on a repository into :attr:`pull_requests`, once.

        :param repository: The repository to list.
        """
        if repository in self.listed_repositories:
            return
        for api_record in self.client_for(repository).all_pull_requests():
            number = PullRequestField.NUMBER.read(api_record)
            self.pull_requests[PullRequestReference(repository, number)] = (
                PullRequestRecord.from_api(api_record)
            )
        self.listed_repositories.add(repository)

    def read_if_present(self, path: str) -> Mapping[str, Any] | None:
        """
        Make one read, treating an absent resource as an answer rather than a failure.

        :param path: The resource's REST path.
        :return: The response, or ``None`` if the API answered that it does not exist.
        :raises GitHubRequestFailed: If the API refused the read for any other reason.
        """
        answer = self.client.attempt_get(path)
        if (
            isinstance(answer.failure, GitHubRequestFailed)
            and answer.failure.status == HTTPStatus.NOT_FOUND
        ):
            return None
        return answer.raise_if_failed()

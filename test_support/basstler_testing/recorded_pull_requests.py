"""
A pull request source answering from a fixed record, for tests that must not reach
GitHub.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from basstler.github.exceptions import GitHubCallFailed
from basstler.github.pull_request_source import PullRequestSource
from basstler.github.pull_request_state import ForkLineage, PullRequestRecord
from basstler.github.repository import PullRequestReference, Repository

# %% recorded pull request state


@dataclass
class RecordedPullRequestSource(PullRequestSource):
    """
    Pull request state answered from a fixed record, noting every lookup made.
    """

    records: dict[PullRequestReference, PullRequestRecord] = field(default_factory=dict)
    """
    The pull requests that exist, by reference.
    """

    issue_urls: dict[PullRequestReference, str] = field(default_factory=dict)
    """
    The issue pages that exist, by repository and number.
    """

    read_failures: dict[Repository, GitHubCallFailed] = field(default_factory=dict)
    """
    Why each repository whose pull requests cannot be read cannot be.
    """

    fork_lineages: dict[Repository, ForkLineage] = field(default_factory=dict)
    """
    What each repository that is a fork was forked from.
    """

    looked_up: list[PullRequestReference] = field(default_factory=list)
    """
    Every pull request asked for, in order.
    """

    def pull_request(self, reference: PullRequestReference) -> PullRequestRecord | None:
        self.looked_up.append(reference)
        return self.records.get(reference)

    def issue_url(self, repository: Repository, number: int) -> str | None:
        return self.issue_urls.get(PullRequestReference(repository, number))

    def read_failure_of(self, repository: Repository) -> GitHubCallFailed | None:
        return self.read_failures.get(repository)

    def fork_lineage_of(self, repository: Repository) -> ForkLineage | None:
        return self.fork_lineages.get(repository)

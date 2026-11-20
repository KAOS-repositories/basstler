"""
The pull requests of a handover's underway items on the repository they were started on,
which the receiver continues on their own: read before continuing them, closed once
handed over, and their branches deleted once the receiver's repository holds the work.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.git.commands import GitCommandRunner
from basstler.git.remote_branch import RemoteBranch
from basstler.github.client import GitHubClient, GitHubReader
from basstler.github.issue import IssueClosing, IssueComment
from basstler.github.repository import PullRequestReference, Repository
from basstler.github.rest_models import RestPullRequestState, RestPullRequestSummary
from basstler.plan.dependencies import DependencyReference
from basstler.plan.handover import PlanHandover

# %% one original


@dataclass(frozen=True)
class OriginalPullRequest(PullRequestReference):
    """
    An underway item's unmerged pull request on the repository it was started on.
    """

    item: DependencyReference
    """
    The item, naming its plan.
    """

    summary: RestPullRequestSummary
    """
    The pull request as it was read, with its branches and state.
    """

    @classmethod
    def read_every_unmerged(
        cls,
        *,
        handover: PlanHandover,
        receiver_repository: Repository,
        client: GitHubReader,
    ) -> list[OriginalPullRequest]:
        """
        :param handover: The handover.
        :param receiver_repository: The repository the receiver continues the items on.
        :param client: Reads the pull requests.
        :return: The unmerged pull request of every item naming a branch and a pull
            request on a repository other than *receiver_repository*, in plan and item
            order.
        """
        originals = [
            cls(
                repository=repository,
                number=item.pull_request_number,
                item=DependencyReference(
                    item_identifier=item.identifier, plan_id=plan.identifier
                ),
                summary=RestPullRequestSummary.from_json(
                    client.get(repository.pull_request_path(item.pull_request_number))
                ),
            )
            for plan in handover.plans
            for item in plan.manifest.items
            for repository in [plan.manifest.repository_of(item)]
            if item.branch
            and item.pull_request_number is not None
            and repository != receiver_repository
        ]
        return [original for original in originals if not original.summary.merged]

    def comment_and_close(self, *, client: GitHubClient, note: str) -> None:
        """
        Comment *note* on the pull request, then close it.

        :param client: Writes the pull request.
        :param note: Why it is closed, in Markdown.
        """
        client.send(
            IssueComment(repository=self.repository, number=self.number, body=note)
        )
        client.send(IssueClosing(repository=self.repository, number=self.number))


@dataclass(frozen=True)
class BranchDeletions:
    """
    What deleting the originals' branches did.
    """

    deleted: tuple[OriginalPullRequest, ...]
    """
    The originals whose branch was deleted, each closed first if it was open.
    """

    kept: tuple[OriginalPullRequest, ...]
    """
    The originals whose branch the receiver's repository lacks or has moved away from,
    left as they were.
    """


# %% the sender's originals of a handover


@dataclass(frozen=True)
class SenderOriginalPullRequests:
    """
    The unmerged pull requests of a handover's underway items on the sender's
    repository, none when the receiver works in that same repository.
    """

    handover: PlanHandover
    """
    The handover, as the sender's notes branch holds it.
    """

    receiver_repository: Repository
    """
    The repository the receiver continues the items on.
    """

    git: GitCommandRunner
    """
    The sender's checkout.
    """

    client: GitHubClient
    """
    Reads and writes the sender's pull requests.
    """

    remote: str = "origin"
    """
    The sender's remote naming the sender's repository.
    """

    def read_unmerged(self) -> list[OriginalPullRequest]:
        """
        :return: Every original on the sender's repository not merged, in plan and item
            order.
        """
        repository = Repository.from_configured_remote(self.git, self.remote)
        return [
            original
            for original in OriginalPullRequest.read_every_unmerged(
                handover=self.handover,
                receiver_repository=self.receiver_repository,
                client=self.client,
            )
            if original.repository == repository
        ]

    def close_open_originals(
        self, *, handover_pull_request: PullRequestReference
    ) -> tuple[OriginalPullRequest, ...]:
        """
        Close every open original, saying where it is handed over.

        :param handover_pull_request: The pull request the handover is offered in.
        :return: The originals closed.
        """
        closed = tuple(
            original
            for original in self.read_unmerged()
            if original.summary.state == RestPullRequestState.OPEN
        )
        for original in closed:
            original.comment_and_close(
                client=self.client,
                note=f"Handed over in {handover_pull_request.url}, to be continued on "
                f"{self.receiver_repository.full_name}.",
            )
        return closed

    def delete_continued_branches(self) -> BranchDeletions:
        """
        Delete the branch of every original whose commit the receiver's branch of the
        same name holds, closing the original first if it is open.

        :return: The originals whose branch was deleted, and those kept.
        """
        deleted = []
        kept = []
        for original in self.read_unmerged():
            continued_commit = RemoteBranch(
                git=self.git,
                name=original.summary.head.name,
                remote=self.receiver_repository.clone_url,
            ).fetch()
            if continued_commit is None or not self.git.contains(
                original.summary.head.object_hash, continued_commit
            ):
                kept.append(original)
                continue
            if original.summary.state == RestPullRequestState.OPEN:
                original.comment_and_close(
                    client=self.client,
                    note="Handed over: continued on "
                    f"{self.receiver_repository.full_name}.",
                )
            self.git.run(
                "push", "--quiet", self.remote, "--delete", original.summary.head.name
            )
            deleted.append(original)
        return BranchDeletions(deleted=tuple(deleted), kept=tuple(kept))

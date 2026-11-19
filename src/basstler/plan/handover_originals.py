"""
The sender's pull requests of a handover's underway items, which the receiver continues
on their own repository: closed once handed over, and their branches deleted once the
receiver's repository holds the work.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.git.commands import GitCommandRunner
from basstler.git.remote_branch import RemoteBranch
from basstler.github.client import GitHubClient
from basstler.github.issue import Issue, IssueClosing, IssueComment
from basstler.github.repository import Repository
from basstler.github.rest_models import RestPullRequestState, RestPullRequestSummary
from basstler.plan.handover import PlanHandover

# %% one original


@dataclass(frozen=True)
class OriginalPullRequest:
    """
    An underway item's unmerged pull request on the sender's repository.
    """

    plan_identifier: str
    """
    The plan holding the item.
    """

    item_identifier: str
    """
    The item's id.
    """

    summary: RestPullRequestSummary
    """
    The pull request as it is now.
    """


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


# %% every original of a handover


@dataclass(frozen=True)
class OriginalPullRequests:
    """
    The originals of a handover's underway items on the sender's repository: every item
    there naming a branch and an unmerged pull request, unless the receiver works in
    that same repository.
    """

    handover: PlanHandover
    """
    The handover, as the sender's notes branch holds it.
    """

    receiver: Repository
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

    def unmerged(self) -> list[OriginalPullRequest]:
        """
        :return: Every original not merged, in plan and item order; none when the
            receiver works in the sender's repository.
        """
        repository = Repository.from_configured_remote(self.git, self.remote)
        if self.receiver == repository:
            return []
        originals = [
            OriginalPullRequest(
                plan_identifier=plan.identifier,
                item_identifier=item.identifier,
                summary=RestPullRequestSummary.from_json(
                    self.client.get(
                        repository.pull_request_path(item.pull_request_number)
                    )
                ),
            )
            for plan in self.handover.plans
            for item in plan.manifest.items
            if item.branch
            and item.pull_request_number is not None
            and plan.manifest.repository_of(item) == repository
        ]
        return [original for original in originals if not original.summary.merged]

    def close(self, *, handover_pull_request: Issue) -> tuple[OriginalPullRequest, ...]:
        """
        Close every open original, saying it is handed over.

        :param handover_pull_request: The pull request the handover is offered in.
        :return: The originals closed.
        """
        closed = tuple(
            original
            for original in self.unmerged()
            if original.summary.state == RestPullRequestState.OPEN
        )
        for original in closed:
            self.close_original(
                original,
                note=f"Handed over in {handover_pull_request.url}, to be continued on "
                f"{self.receiver.full_name}.",
            )
        return closed

    def delete_branches(self) -> BranchDeletions:
        """
        Delete the branch of every original whose commit the receiver's branch of the
        same name holds, closing it first if it is open.

        :return: The originals whose branch was deleted, and those kept.
        """
        deleted = []
        kept = []
        for original in self.unmerged():
            continued = RemoteBranch(
                git=self.git,
                name=original.summary.head.name,
                remote=self.receiver.clone_url,
            ).fetch()
            if continued is None or not self.git.contains(
                original.summary.head.object_hash, continued
            ):
                kept.append(original)
                continue
            if original.summary.state == RestPullRequestState.OPEN:
                self.close_original(
                    original,
                    note=f"Handed over: continued on {self.receiver.full_name}.",
                )
            self.git.run(
                "push", "--quiet", self.remote, "--delete", original.summary.head.name
            )
            deleted.append(original)
        return BranchDeletions(deleted=tuple(deleted), kept=tuple(kept))

    def close_original(self, original: OriginalPullRequest, *, note: str) -> None:
        """
        Comment *note* on an original, then close it.

        :param original: An open original.
        :param note: Why it is closed, in Markdown.
        """
        repository = Repository.from_configured_remote(self.git, self.remote)
        self.client.send(
            IssueComment(
                repository=repository, number=original.summary.number, body=note
            )
        )
        self.client.send(
            IssueClosing(repository=repository, number=original.summary.number)
        )

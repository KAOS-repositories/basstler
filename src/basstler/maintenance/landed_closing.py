"""
Closing the open fork pull requests whose work has already landed upstream.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.github.constants import MaintenanceText
from basstler.github.pull_request_record import PullRequestField
from basstler.github.repository_access import ForkPullRequests
from basstler.github.tooling_labels import GitHubLabel
from basstler.stack.checkout import CurrentCheckout
from basstler.stack.label_write import LabelWrite
from basstler.stack.model import Stack, StackBranch

# %% what was closed


@dataclass(frozen=True)
class ClosedAsLanded:
    """
    One fork pull request closed because its work had landed upstream.
    """

    branch: str
    """
    The pull request's head branch.
    """

    pull_request_number: int
    """
    The fork pull request that was closed.
    """


# %% closing them


@dataclass(frozen=True)
class LandedPullRequestClosing:
    """
    Closes every open fork pull request whose commits are all in the upstream base.

    GitHub records no merge for such a pull request when it is based on another branch,
    so it stays open, and the plan site reads it as unfinished, until it is closed and
    labelled.
    """

    stack: Stack
    """
    The derived stack, which says which branches have landed.
    """

    fork: ForkPullRequests
    """
    The fork to read pull requests from and write them back to.
    """

    def close(self) -> tuple[ClosedAsLanded, ...]:
        """
        Label each landed pull request as merged, close it and say why.

        A branch with no commit beyond its base is left open: it is an ancestor of the
        upstream base as a landed branch is, but nothing of it landed.

        :return: One entry per pull request closed, parent before child.
        """
        closed = []
        for branch in self.stack.landed_branches():
            if not self.has_commits_of_its_own(branch):
                continue
            self.label_merged(branch)
            self.fork.close_pull_request(branch.pull_request_number)
            self.fork.add_comment(
                branch.pull_request_number,
                MaintenanceText.LANDED_COMMENT.format(
                    branch=branch.name, base=self.upstream_base
                ),
            )
            closed.append(ClosedAsLanded(branch.name, branch.pull_request_number))
        return tuple(closed)

    @property
    def upstream_base(self) -> str:
        """
        :return: The upstream base reference the landed branches are contained in.
        """
        configuration = self.stack.configuration
        return f"{configuration.upstream_remote}/{configuration.upstream_base}"

    def has_commits_of_its_own(self, branch: StackBranch) -> bool:
        """
        :param branch: A landed branch of the stack.
        :return: Whether the fork's copy of it has a commit its base lacks; ``False``
            when either cannot be read.
        """
        configuration = self.stack.configuration
        ahead = CurrentCheckout.commit_count(
            f"{configuration.reference_on_fork(branch.parent)}"
            f"..{configuration.reference_on_fork(branch.name)}"
        )
        return ahead is not None and ahead > 0

    def label_merged(self, branch: StackBranch) -> None:
        """
        Add the merged label to what the pull request carries now.

        :param branch: The landed branch whose pull request is labelled.
        """
        number = branch.pull_request_number
        labels = PullRequestField.LABELS.read(self.fork.pull_request(number), number)
        self.fork.replace_labels(
            number, LabelWrite.replacing(labels, added=[GitHubLabel.MERGED]).labels
        )

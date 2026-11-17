"""
Closing the open fork pull requests whose work has already landed upstream.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.github.constants import MaintenanceText
from basstler.github.constants import MaintenanceNotice
from basstler.maintenance.fork_pull_request_action import ForkPullRequestAction
from basstler.github.branch_pull_request import BranchPullRequest
from basstler.stack.checkout import CurrentCheckout
from basstler.stack.model import StackBranch
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

# %% what was closed


@dataclass(frozen=True)
class ClosedAsLanded(BranchPullRequest):
    """
    One fork pull request closed because its work had landed upstream.
    """


# %% closing them


@dataclass(frozen=True)
class LandedPullRequestClosing(ForkPullRequestAction):
    """
    Closes every open fork pull request whose commits are all in the upstream base.

    GitHub records no merge for such a pull request when it is based on another branch,
    so it stays open until it is closed. A branch with no commit beyond its base, or whose
    commits cannot be counted (which is warned about), is left open.
    """

    def apply(self) -> tuple[ClosedAsLanded, ...]:
        closed = []
        for branch in self.stack.landed_branches():
            if not self.has_commits_of_its_own(branch):
                continue
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
            when either cannot be read, which is warned about.
        """
        configuration = self.stack.configuration
        base = configuration.reference_on_fork(branch.parent)
        head = configuration.reference_on_fork(branch.name)
        ahead = CurrentCheckout.commit_count(f"{base}..{head}")
        if ahead is None:
            logger.warning(
                MaintenanceNotice.LANDED_BRANCH_UNREADABLE.format(
                    branch=branch.name, base=base, head=head
                )
            )
            return False
        return ahead > 0

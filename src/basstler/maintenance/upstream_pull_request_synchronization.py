"""
Keeping each fork pull request's record of its upstream review - the in-review label and
the link to the upstream pull request - in step with the upstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from basstler.github.pull_request_description import (
    PullRequestDescription,
    UpstreamPullRequestLink,
)
from basstler.github.pull_request_record import (
    PullRequestField,
)
from basstler.maintenance.fork_pull_request_action import ForkPullRequestAction
from basstler.github.branch_pull_request import BranchPullRequest
from basstler.stack.label_write import LabelWrite
from basstler.stack.model import BranchStatus, StackBranch


class UpstreamPullRequestSynchronizationAction(StrEnum):
    """
    What was written to a fork pull request to bring its record of the upstream review
    in step.
    """

    LABEL_ADDED = "in-review label added"
    """
    The in-review label was added, because an upstream pull request opened from the
    branch is open.
    """

    LABEL_REMOVED = "in-review label removed"
    """
    The in-review label was removed, because no upstream pull request opened from the
    branch is open.
    """

    LINK_WRITTEN = "upstream link written"
    """
    The description now links the open upstream pull request opened from the branch.
    """

    LINK_REMOVED = "upstream link removed"
    """
    The description's link to an upstream pull request was removed, because none opened
    from the branch is open.
    """


@dataclass(frozen=True)
class UpstreamPullRequestSynchronizationChange(BranchPullRequest):
    """
    One write bringing a fork pull request's record of its upstream review in step.
    """

    action: UpstreamPullRequestSynchronizationAction
    """
    What was written.
    """


@dataclass(frozen=True)
class UpstreamPullRequestSynchronization(ForkPullRequestAction):
    """
    The in-review label and the upstream pull request link on each fork pull request,
    kept in step with the open upstream pull request opened from its branch.
    """

    def apply(self) -> list[UpstreamPullRequestSynchronizationChange]:
        changes: list[UpstreamPullRequestSynchronizationChange] = []
        for branch in self.stack.maintained_branches():
            if branch.status is BranchStatus.MERGED:
                continue
            link = self.upstream_link_of(branch)
            if self.label_in_step(branch.labels, link) and self.link_in_step(
                branch.upstream_link, link
            ):
                continue
            changes.extend(self.write(branch, link))
        return changes

    def upstream_link_of(self, branch: StackBranch) -> UpstreamPullRequestLink | None:
        """
        :param branch: A branch of the stack.
        :return: The link to the open upstream pull request opened from it, ``None``
            when none is open.
        """
        if branch.upstream_pull_request is None:
            return None
        return UpstreamPullRequestLink(
            self.stack.configuration.upstream_repository, branch.upstream_pull_request
        )

    def label_in_step(
        self, labels: list[str], link: UpstreamPullRequestLink | None
    ) -> bool:
        """
        :param labels: The labels a pull request carries.
        :param link: The upstream pull request it should link.
        :return: Whether it carries the in-review label exactly when *link* exists.
        """
        return (self.stack.configuration.in_review_label in labels) == (
            link is not None
        )

    @staticmethod
    def link_in_step(
        linked_url: str | None, link: UpstreamPullRequestLink | None
    ) -> bool:
        """
        :param linked_url: The upstream pull request URL a description links.
        :param link: The upstream pull request it should link.
        :return: Whether the description links exactly *link*.
        """
        return linked_url == (None if link is None else link.url)

    def write(
        self, branch: StackBranch, link: UpstreamPullRequestLink | None
    ) -> list[UpstreamPullRequestSynchronizationChange]:
        """
        Write the label and the link that disagree with what *branch*'s pull request
        carries now.

        :param branch: The branch whose pull request is written.
        :param link: The upstream pull request it should link.
        :return: The writes made.
        """
        number = branch.pull_request_number
        current = self.fork.pull_request(number)
        labels = PullRequestField.LABELS.read(current, number)
        description = PullRequestDescription(
            str(PullRequestField.BODY.read(current, number) or "")
        )
        actions = [
            action
            for action in (
                self.write_label(number, labels, link),
                self.write_link(number, description, link),
            )
            if action is not None
        ]
        return [
            UpstreamPullRequestSynchronizationChange(branch.name, number, action)
            for action in actions
        ]

    def write_label(
        self, number: int, labels: list[str], link: UpstreamPullRequestLink | None
    ) -> UpstreamPullRequestSynchronizationAction | None:
        """
        :param number: The fork pull request to write.
        :param labels: The labels it carries now.
        :param link: The upstream pull request it should link.
        :return: What was written, ``None`` when its label was already in step.
        """
        if self.label_in_step(labels, link):
            return None
        label = self.stack.configuration.in_review_label
        if link is None:
            write = LabelWrite.replacing(labels, removed=[label])
            action = UpstreamPullRequestSynchronizationAction.LABEL_REMOVED
        else:
            write = LabelWrite.replacing(labels, added=[label])
            action = UpstreamPullRequestSynchronizationAction.LABEL_ADDED
        self.fork.replace_labels(number, write.labels)
        return action

    def write_link(
        self,
        number: int,
        description: PullRequestDescription,
        link: UpstreamPullRequestLink | None,
    ) -> UpstreamPullRequestSynchronizationAction | None:
        """
        :param number: The fork pull request to write.
        :param description: The description it carries now.
        :param link: The upstream pull request it should link.
        :return: What was written, ``None`` when its link was already in step.
        """
        if self.link_in_step(description.upstream_link, link):
            return None
        self.fork.set_description(number, description.with_upstream_link(link))
        if link is None:
            return UpstreamPullRequestSynchronizationAction.LINK_REMOVED
        return UpstreamPullRequestSynchronizationAction.LINK_WRITTEN

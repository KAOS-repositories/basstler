"""
Continuing a handover's underway items on the receiver's own repository: each item whose
pull request has not merged has its branch, and the branch it stacks on, pushed there,
and its pull request opened again from them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from basstler.git.branch import Branch
from basstler.git.commands import GitCommandRunner
from basstler.git.remote import Remote
from basstler.git.remote_branch import RemoteBranch
from basstler.github.client import GitHubClient
from basstler.github.issue import Issue
from basstler.github.pull_request import NewPullRequest
from basstler.github.repository import PullRequestReference, Repository
from basstler.github.repository_access import PullRequestListState
from basstler.plan.handover import PlanHandover
from basstler.plan.handover_originals import OriginalPullRequest
from basstler.render_common import TemplatePage
from basstler.class_property import classproperty
from basstler.locations import PlanHandoverLocation

# %% what was continued


@dataclass(frozen=True)
class ItemContinuation:
    """
    An underway item's pull request, opened again on the receiver's repository.
    """

    original: OriginalPullRequest
    """
    The pull request it was started in, which keeps its review threads.
    """

    continued: PullRequestReference
    """
    The pull request on the receiver's repository the item now names.
    """


@dataclass(frozen=True)
class ContinuedHandover:
    """
    A handover whose underway items name the pull requests continuing them.
    """

    handover: PlanHandover
    """
    The handover, every plan on the receiver's repository.
    """

    continuations: tuple[ItemContinuation, ...]
    """
    Every item continued, in plan and item order.
    """


# %% continuing them


@dataclass(frozen=True)
class UnderwayWork:
    """
    Continues the underway items of handed-over plans on the receiver's repository.

    An item is continued when it names a branch and a pull request not merged on another
    repository. Running it again reuses the branches and pull requests already
    continued.
    """

    git: GitCommandRunner
    """
    The receiver's checkout.
    """

    client: GitHubClient
    """
    Reads the original pull requests and opens the receiver's.
    """

    remote: str = "origin"
    """
    The receiver's remote naming their repository.
    """

    @property
    def repository(self) -> Repository:
        """
        The receiver's repository.
        """
        return Repository.from_configured_remote(self.git, self.remote)

    def continue_underway_items(self, handover: PlanHandover) -> ContinuedHandover:
        """
        :param handover: The handover taken over.
        :return: It with every plan moved onto the receiver's repository and every
            continued item naming its new pull request.
        """
        repository = self.repository
        continuations = tuple(
            self.reopen_on_receiver(original)
            for original in OriginalPullRequest.read_every_unmerged(
                handover=handover, receiver_repository=repository, client=self.client
            )
        )
        return ContinuedHandover(
            handover=PlanHandover(
                plans=tuple(
                    plan.moved_to_repository(repository).with_pull_requests(
                        {
                            continuation.original.item.item_identifier: (
                                continuation.continued.number
                            )
                            for continuation in continuations
                            if continuation.original.item.plan_id == plan.identifier
                        }
                    )
                    for plan in handover.plans
                ),
                progress_notes=handover.progress_notes,
                repository_rules=handover.repository_rules,
            ),
            continuations=continuations,
        )

    def reopen_on_receiver(self, original: OriginalPullRequest) -> ItemContinuation:
        """
        Copy the original's branch, and the branch it merges into where the receiver's
        repository has none, to the receiver's repository, and open the pull request
        there as a draft unless one is open already.

        :param original: An unmerged pull request on another repository.
        :raises GitCommandFailed: If the receiver's repository has the original's branch
            at a commit the copy does not descend from.
        :return: The continuation.
        """
        repository = self.repository
        head = Branch(repository, original.summary.head.name)
        base = Branch(repository, original.summary.base.name)
        self.copy_branch_to_receiver(
            Branch(original.repository, head.name),
            replace=True,
        )
        self.copy_branch_to_receiver(
            Branch(original.repository, base.name),
            replace=False,
        )
        opening = NewPullRequest(
            base=base,
            head=head,
            title=original.summary.title,
            body=(
                f"Continues {original.url}, handed over with basstler; its review "
                "threads and checks stay there."
            ),
        )
        already_open = self.client.get_entries(
            PullRequestListState.OPEN.path_between(opening)
        )
        opened = Issue.from_json(
            already_open[0] if already_open else self.client.send(opening)
        )
        return ItemContinuation(
            original=original,
            continued=PullRequestReference(repository=repository, number=opened.number),
        )

    def copy_branch_to_receiver(
        self, branch: Branch[Repository], *, replace: bool
    ) -> None:
        """
        Push *branch* to the receiver's repository under the same name.

        :param branch: A branch of another repository.
        :param replace: Whether to push it where the receiver's repository has it
            already; it is pushed without force either way, so a branch that moved
            elsewhere there is never overwritten.
        :raises GitCommandFailed: If the receiver's branch is at a commit the pushed one
            does not descend from.
        """
        if (
            not replace
            and RemoteBranch(Remote(self.git, self.remote), branch.name).exists()
        ):
            return
        fetched = RemoteBranch(
            Remote(self.git, branch.repository.clone_url), branch.name
        )
        fetched.fetch()
        self.git.run(
            "push",
            "--quiet",
            self.remote,
            f"{fetched.local_reference}:{branch.reference}",
        )


# %% importing


@dataclass(frozen=True)
class HandoverImport:
    """
    Saves a handover onto the receiver's notes branch, first continuing its underway
    items on the receiver's repository unless told not to.
    """

    project_root: Path
    """
    The receiver's checkout, whose notes branch receives the handover.
    """

    client: GitHubClient
    """
    Reads and writes the sender's and the receiver's pull requests.
    """

    continues_underway_work: bool = True
    """
    Whether underway items of plans on another repository are continued on the
    receiver's, rather than left naming the sender's pull requests.
    """

    def save(self, handover: PlanHandover) -> ContinuedHandover:
        """
        :param handover: The handover taken over.
        :raises PlanAlreadyTrackedError: If the notes branch already holds one of its
            plans.
        :return: The handover as saved, with the items continued.
        """
        continued = (
            UnderwayWork(
                git=GitCommandRunner(self.project_root), client=self.client
            ).continue_underway_items(handover)
            if self.continues_underway_work
            else ContinuedHandover(handover=handover, continuations=())
        )
        continued.handover.save_to_notes_branch(project_root=self.project_root)
        return continued


@dataclass(frozen=True)
class TakenOverComment(TemplatePage):
    """
    The comment a handover pull request is closed with once it is taken over.
    """

    continued: ContinuedHandover
    """
    The handover as taken over.
    """

    notes_branch: str
    """
    The notes branch it was saved onto.
    """

    @classproperty
    def template(cls) -> str:
        return PlanHandoverLocation.TAKEN_OVER_TEMPLATE.name

    def render(self) -> str:
        """
        :return: The comment, in Markdown.
        """
        return self.render_template(
            continued=self.continued, notes_branch=self.notes_branch
        )

"""
Continuing a handover's underway items on the receiver's own repository: each item whose
pull request is still open has its branch, and the branch it stacks on, pushed there, and
its pull request opened again from them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubClient
from basstler.github.issue import Issue
from basstler.github.pull_request import NewPullRequest
from basstler.github.repository import Repository, RepositoryBranch
from basstler.github.repository_access import PullRequestListState
from basstler.github.rest_models import RestPullRequestState, RestPullRequestSummary
from basstler.plan.handover import HandoverPlan, PlanHandover
from basstler.plan.model import PlanItem
from basstler.render_common import TemplatePage
from basstler.class_property import classproperty
from basstler.locations import PlanHandoverLocation

# %% where it is kept


class UnderwayBranchReference(StrEnum):
    """
    Where continuing an item keeps a branch it fetched from the sender's repository.
    """

    FETCHED = "refs/basstler/plan-handover-underway"
    """
    The branch last fetched to be pushed to the receiver's repository.
    """


# %% what was continued


@dataclass(frozen=True)
class ItemContinuation:
    """
    An underway item's pull request, opened again on the receiver's repository.
    """

    plan_identifier: str
    """
    The plan holding the item.
    """

    item_identifier: str
    """
    The item's id.
    """

    original: RestPullRequestSummary
    """
    The pull request on the sender's repository, which keeps its review threads.
    """

    continued: Issue
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

    An item is continued when its plan is on another repository and it names a branch
    and a pull request still open there. Running it again reuses the branches and pull
    requests already continued.
    """

    git: GitCommandRunner
    """
    The receiver's checkout.
    """

    client: GitHubClient
    """
    Reads the sender's pull requests and opens the receiver's.
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

    def continued(self, handover: PlanHandover) -> ContinuedHandover:
        """
        :param handover: The handover taken over.
        :return: It with every plan rehomed onto the receiver's repository and every
            continued item naming its new pull request.
        """
        repository = self.repository
        continuations = []
        for plan in handover.plans:
            if plan.manifest.default_repository == repository:
                continue
            for item in plan.manifest.items:
                if not item.branch or item.pull_request_number is None:
                    continue
                continuation = self.continue_item(plan=plan, item=item)
                if continuation is not None:
                    continuations.append(continuation)
        return ContinuedHandover(
            handover=PlanHandover(
                plans=tuple(
                    plan.rehomed(repository).with_pull_requests(
                        {
                            continuation.item_identifier: continuation.continued.number
                            for continuation in continuations
                            if continuation.plan_identifier == plan.identifier
                        }
                    )
                    for plan in handover.plans
                ),
                progress_notes=handover.progress_notes,
                repository_rules=handover.repository_rules,
            ),
            continuations=tuple(continuations),
        )

    def continue_item(
        self, *, plan: HandoverPlan, item: PlanItem
    ) -> ItemContinuation | None:
        """
        Push the item's branch and the branch its pull request merges into to the
        receiver's repository, the latter only where it has none, and open the pull
        request there as a draft unless one is open already.

        :param plan: The plan holding the item.
        :param item: An item naming a branch and a pull request.
        :raises GitCommandFailedError: If the receiver's repository has the item's branch
            at another commit.
        :return: The continuation, ``None`` when the pull request is no longer open.
        """
        source = plan.manifest.repository_of(item)
        original = RestPullRequestSummary.from_json(
            self.client.get(source.pull_request_path(item.pull_request_number))
        )
        if original.state != RestPullRequestState.OPEN:
            return None
        self.push_branch(source=source, branch=original.head.name, replace=True)
        self.push_branch(source=source, branch=original.base.name, replace=False)
        repository = self.repository
        opening = NewPullRequest(
            base=RepositoryBranch(repository=repository, name=original.base.name),
            head=RepositoryBranch(repository=repository, name=original.head.name),
            title=original.title,
            body=(
                f"Continues {original.page_url}, handed over with basstler; its "
                "review threads and checks stay there."
            ),
        )
        already_open = self.client.get_pages(
            PullRequestListState.OPEN.path_between(opening)
        )
        continued = (
            Issue.from_json(already_open[0])
            if already_open
            else Issue.from_json(self.client.send(opening))
        )
        return ItemContinuation(
            plan_identifier=plan.identifier,
            item_identifier=item.identifier,
            original=original,
            continued=continued,
        )

    def push_branch(self, *, source: Repository, branch: str, replace: bool) -> None:
        """
        Push *source*'s *branch* to the receiver's repository.

        :param source: The repository the branch is on.
        :param branch: The branch.
        :param replace: Whether to push it where the receiver's repository has it
            already; it is pushed without force either way, so a branch that moved
            elsewhere there is never overwritten.
        :raises GitCommandFailedError: If the receiver's branch is at a commit the
            pushed one does not descend from.
        """
        if not replace and self.git.run("ls-remote", "--heads", self.remote, branch):
            return
        self.git.run(
            "fetch",
            "--quiet",
            "--no-write-fetch-head",
            source.clone_url,
            f"+refs/heads/{branch}:{UnderwayBranchReference.FETCHED}",
        )
        self.git.run(
            "push",
            "--quiet",
            self.remote,
            f"{UnderwayBranchReference.FETCHED}:refs/heads/{branch}",
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
            ).continued(handover)
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

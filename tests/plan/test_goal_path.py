"""
Tests for basstler.plan.goal_path: the ordered path from the plans to a goal's targets.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from basstler.github.pull_request_state import PullRequestRecord, PullRequestState
from basstler.github.repository import PullRequestReference, Repository
from basstler.locations import ProjectLocation
from basstler.plan.dependencies import DependencyReference, PlanDirectory
from basstler.plan.exceptions import UnresolvedGoalReferenceError
from basstler.plan.goal import Goal
from basstler.plan.goal_path import GoalPath, OwnerMove, OwnerSituation, PathStep
from basstler.plan.item_action import ItemAction, ResolveAction, StartNowAction
from basstler.plan.model import ItemStatus
from basstler.plan.structure import Item, Plan

from ..constants.paths import DatasetLocation
from ..recorded_pull_requests import RecordedPullRequestSource

# %% the goal and the plans it spans


class GoalPlanId(StrEnum):
    """
    The plans the goal's path runs through.
    """

    REVIEW_TRIAGE = "review-triage"
    """
    The plan holding the goal's targets.
    """

    PACKAGES = "basstler-packages"
    """
    The plan one target depends into.
    """


class StepId(StrEnum):
    """
    The items the tests single out, each for the state its plan records it in.
    """

    NOT_STARTED_BEHIND_DRAFTS = "rule-fix-triage"
    """
    Not started, depending on two items whose pull requests are drafts.
    """

    IN_PROGRESS = "move-triage"
    """
    In progress, depending on nothing.
    """

    BEHIND_ANOTHER_PLAN = "action-plan-triage"
    """
    A target depending on :attr:`IN_ANOTHER_PLAN`.
    """

    IN_ANOTHER_PLAN = "uv-workspace"
    """
    In :attr:`GoalPlanId.PACKAGES`.
    """

    STACKED_WITH_PULL_REQUEST = "actions-marking"
    """
    In progress with a pull request, depending on an item that has one too.
    """

    OUTSIDE_THE_PATH = "pypi-release"
    """
    In :attr:`GoalPlanId.PACKAGES`, which no target depends on.
    """


GOAL = Goal.from_yaml(
    (
        DatasetLocation.GOAL_PLANS
        / ProjectLocation.PLAN_GOALS.name
        / "mechanical-files-viewed.yaml"
    ).read_text()
)
"""
The goal every path is computed for.
"""


def reference_of(
    item_identifier: str, plan_id: str = GoalPlanId.REVIEW_TRIAGE
) -> DependencyReference:
    """
    :param item_identifier: An item's id.
    :param plan_id: The plan holding it.
    :return: The reference a path names that item by.
    """
    return DependencyReference(item_identifier=item_identifier, plan_id=plan_id)


@pytest.fixture
def plan_directory() -> PlanDirectory:
    """
    :return: The plans the goal spans, read afresh.
    """
    return PlanDirectory(DatasetLocation.GOAL_PLANS)


def pull_request_reference_of(plan: Plan, item: Item) -> PullRequestReference:
    """
    :param plan: The plan holding the item.
    :param item: An item with a pull request.
    :return: That pull request.
    """
    return PullRequestReference(
        Repository.parse(item.repository or plan.default_repository),
        item.pull_request_number,
    )


def recorded_pull_requests(
    draft: bool, merged_items: frozenset[str] = frozenset()
) -> RecordedPullRequestSource:
    """
    :param draft: Whether every open pull request is a draft.
    :param merged_items: The ids of the items whose pull requests have merged.
    :return: A pull request for every item of the spanned plans that names one.
    """
    directory = PlanDirectory(DatasetLocation.GOAL_PLANS)
    records = {}
    for plan in map(directory.plan, GoalPlanId):
        for item in plan.items:
            if item.pull_request_number is None:
                continue
            merged = item.identifier in merged_items
            records[pull_request_reference_of(plan, item)] = PullRequestRecord(
                state=PullRequestState.CLOSED if merged else PullRequestState.OPEN,
                draft=draft and not merged,
                merged_at="2026-11-15T00:00:00+00:00" if merged else None,
            )
    return RecordedPullRequestSource(records=records)


def path_with(
    plan_directory: PlanDirectory, pull_requests: RecordedPullRequestSource
) -> GoalPath:
    """
    :return: The goal's path over the plans, with those pull requests.
    """
    return GoalPath.compute(GOAL, plan_directory, pull_requests)


def step_of(path: GoalPath, reference: DependencyReference) -> PathStep:
    """
    :return: The path's step for the referenced item.
    """
    (step,) = [step for step in path.steps if step.reference == reference]
    return step


# %% which items a path holds


class TestTheItemsOnAPath:
    """
    A path holds the targets and everything they depend on, across plans, once each.
    """

    def test_every_target_is_a_step(self, plan_directory: PlanDirectory):
        """
        Each target the goal names is on its path.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert set(GOAL.target_references) <= {step.reference for step in path.steps}

    def test_a_dependency_in_another_plan_is_a_step(
        self, plan_directory: PlanDirectory
    ):
        """
        A dependency written as another plan's item is followed into that plan.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert reference_of(StepId.IN_ANOTHER_PLAN, GoalPlanId.PACKAGES) in [
            step.reference for step in path.steps
        ]

    def test_an_item_no_target_depends_on_is_left_out(
        self, plan_directory: PlanDirectory
    ):
        """
        A plan being on the path does not put its unrelated items on it.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert reference_of(StepId.OUTSIDE_THE_PATH, GoalPlanId.PACKAGES) not in [
            step.reference for step in path.steps
        ]

    def test_every_step_comes_after_the_steps_it_depends_on(
        self, plan_directory: PlanDirectory
    ):
        """
        The steps are in an order that respects every dependency.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        position = {step.reference: index for index, step in enumerate(path.steps)}

        assert all(
            position[dependency] < position[step.reference]
            for step in path.steps
            for dependency in step.dependencies
        )

    def test_a_target_naming_no_item_is_refused(self, plan_directory: PlanDirectory):
        """
        A path is not computed around a target that does not exist.
        """
        goal = Goal(
            identifier=GOAL.identifier,
            title=GOAL.title,
            targets=[reference_of("no-such-item").text],
        )

        with pytest.raises(UnresolvedGoalReferenceError):
            GoalPath.compute(goal, plan_directory, RecordedPullRequestSource())


# %% what a step waits for and what starts it


class TestWhatAStepWaitsFor:
    """
    A not-started step waits for each dependency that is not ready to build on; a step
    under way waits for nothing.
    """

    def test_a_not_started_step_waits_for_its_draft_dependencies(
        self, plan_directory: PlanDirectory
    ):
        """
        Draft dependencies hold a not-started step back and leave it no action.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        step = step_of(path, reference_of(StepId.NOT_STARTED_BEHIND_DRAFTS))

        assert (step.awaited, step.action) == (step.dependencies, None)

    def test_it_starts_once_its_dependencies_are_ready_for_review(
        self, plan_directory: PlanDirectory
    ):
        """
        Dependencies out of draft release the step to be started.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=False))
        step = step_of(path, reference_of(StepId.NOT_STARTED_BEHIND_DRAFTS))

        assert (step.awaited, type(step.action)) == ((), StartNowAction)

    def test_a_step_under_way_is_resumed(self, plan_directory: PlanDirectory):
        """
        A step in progress gets the action its item's state calls for.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        step = step_of(path, reference_of(StepId.IN_PROGRESS))

        assert step.action == ItemAction.from_item_state(
            GoalPlanId.REVIEW_TRIAGE, step.item, dependencies_are_ready=True
        )
        assert isinstance(step.action, ResolveAction)

    def test_a_merged_step_is_finished_and_has_no_action(
        self, plan_directory: PlanDirectory
    ):
        """
        A merged pull request finishes its step whatever the plan's status says.
        """
        path = path_with(
            plan_directory,
            recorded_pull_requests(
                draft=True, merged_items=frozenset({StepId.IN_PROGRESS})
            ),
        )
        step = step_of(path, reference_of(StepId.IN_PROGRESS))

        assert (step.action, step in path.finished_steps) == (None, True)


# %% the groups a path is read in


class TestTheGroupsOfAPath:
    """
    Steps are grouped by what they wait for, the group waiting for nothing first.
    """

    def test_the_first_group_waits_for_nothing(self, plan_directory: PlanDirectory):
        """
        The steps to act on now come first.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert path.groups[0].awaited == ()

    def test_steps_waiting_for_the_same_items_share_a_group(
        self, plan_directory: PlanDirectory
    ):
        """
        One group per distinct set of awaited items.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert all(
            step.awaited == group.awaited
            for group in path.groups
            for step in group.steps
        )
        assert len({group.awaited for group in path.groups}) == len(path.groups)

    def test_a_group_comes_after_the_groups_holding_what_it_waits_for(
        self, plan_directory: PlanDirectory
    ):
        """
        Reading the groups top to bottom never meets a step before what it waits for.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        group_position = {
            step.reference: index
            for index, group in enumerate(path.groups)
            for step in group.steps
        }

        assert all(
            group_position[awaited] < index
            for index, group in enumerate(path.groups)
            for awaited in group.awaited
        )

    def test_finished_steps_are_in_no_group(self, plan_directory: PlanDirectory):
        """
        Finished steps are listed apart from the steps still to take.
        """
        path = path_with(
            plan_directory,
            recorded_pull_requests(
                draft=True, merged_items=frozenset({StepId.IN_PROGRESS})
            ),
        )

        assert not {step.reference for step in path.finished_steps} & {
            step.reference for group in path.groups for step in group.steps
        }

    def test_the_next_step_is_the_first_one_with_an_action(
        self, plan_directory: PlanDirectory
    ):
        """
        The next step is the first of the steps to act on now.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert path.next_step == path.groups[0].steps[0]
        assert path.next_step.action is not None


# %% the report


class TestThePathReport:
    """
    The report names every unfinished step with its command and what it waits for.
    """

    def test_each_step_reports_its_action_s_command(
        self, plan_directory: PlanDirectory
    ):
        """
        The report carries each step's command, and none for a waiting step.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        reported = {
            step.reference: step.command
            for group in path.report().groups
            for step in group.steps
        }

        assert reported == {
            step.reference.text: step.action.command if step.action else None
            for group in path.groups
            for step in group.steps
        }

    def test_the_text_names_the_next_step_s_command(
        self, plan_directory: PlanDirectory
    ):
        """
        The printed path's second line gives the next command.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert path.next_step.action.command in path.render().splitlines()[1]

    def test_a_not_started_status_is_reported_as_the_plan_records_it(
        self, plan_directory: PlanDirectory
    ):
        """
        The report passes the plan's own status through.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        (reported,) = [
            step
            for group in path.report().groups
            for step in group.steps
            if step.reference == reference_of(StepId.NOT_STARTED_BEHIND_DRAFTS).text
        ]

        assert reported.status == ItemStatus.NOT_STARTED


# %% the owner's moves


class TestTheOwnersMoves:
    """
    A step whose pull request waits on the owner names the owner's move and the steps
    that move releases.
    """

    def test_a_draft_pull_request_waits_for_the_owners_review(
        self, plan_directory: PlanDirectory
    ):
        """
        A step with a draft pull request asks the owner to review it and mark it ready.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        step = step_of(path, reference_of(StepId.IN_PROGRESS))

        assert step.owner_move == OwnerMove(
            situation=OwnerSituation.DRAFT_AWAITING_REVIEW,
            pull_request_number=step.item.pull_request_number,
        )

    def test_a_ready_pull_request_waits_for_the_owners_merge(
        self, plan_directory: PlanDirectory
    ):
        """
        A step whose pull request is out of draft asks the owner to merge it.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=False))
        step = step_of(path, reference_of(StepId.IN_PROGRESS))

        assert step.owner_move == OwnerMove(
            situation=OwnerSituation.READY_TO_MERGE,
            pull_request_number=step.item.pull_request_number,
        )

    def test_a_merge_comes_after_the_unmerged_dependencies(
        self, plan_directory: PlanDirectory
    ):
        """
        A ready pull request is merged only after the steps it depends on have merged.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=False))
        step = step_of(path, reference_of(StepId.STACKED_WITH_PULL_REQUEST))

        assert step.owner_move.after == step.dependencies

    def test_a_merged_dependency_no_longer_holds_a_merge_back(
        self, plan_directory: PlanDirectory
    ):
        """
        Once every dependency has merged, the merge waits for nothing.
        """
        unmerged = step_of(
            path_with(plan_directory, recorded_pull_requests(draft=False)),
            reference_of(StepId.STACKED_WITH_PULL_REQUEST),
        )
        merged_items = frozenset(
            dependency.item_identifier for dependency in unmerged.dependencies
        )
        path = path_with(
            plan_directory,
            recorded_pull_requests(draft=False, merged_items=merged_items),
        )

        step = step_of(path, reference_of(StepId.STACKED_WITH_PULL_REQUEST))
        assert step.owner_move.after == ()

    def test_a_step_without_a_pull_request_has_no_owner_move(
        self, plan_directory: PlanDirectory
    ):
        """
        Nothing waits on the owner before a pull request exists.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        step = step_of(path, reference_of(StepId.NOT_STARTED_BEHIND_DRAFTS))

        assert step.owner_move is None

    def test_a_step_releases_the_steps_waiting_for_it(
        self, plan_directory: PlanDirectory
    ):
        """
        The steps a move releases are exactly those that wait for its step.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        waiting = step_of(path, reference_of(StepId.NOT_STARTED_BEHIND_DRAFTS))

        for awaited in waiting.awaited:
            assert waiting.reference in path.references_released_by(
                step_of(path, awaited)
            )

    def test_the_report_states_the_move_and_what_it_releases(
        self, plan_directory: PlanDirectory
    ):
        """
        A reported step carries the owner's move as a sentence and the released steps.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        step = step_of(path, reference_of(StepId.IN_PROGRESS))
        (reported,) = [
            entry
            for group in path.report().groups
            for entry in group.steps
            if entry.reference == step.reference.text
        ]

        assert reported.owner_move == step.owner_move.description
        assert reported.releases == [
            reference.text for reference in path.references_released_by(step)
        ]

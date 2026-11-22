"""
Tests for basstler.plan.goal_path: the ordered path from the plans to a goal's targets.
"""

from __future__ import annotations
import pytest
from basstler.plan.dependencies import PlanDirectory
from basstler.plan.exceptions import UnresolvedGoalReferenceError
from basstler.plan.goal import Goal
from basstler.plan.goal_path import (
    OWNER_PREFIX,
    GoalPath,
    OwnerSituation,
    PullRequestMove,
)
from basstler.plan.item_action import ItemAction, ResolveAction, StartNowAction
from basstler.plan.model import ItemStatus
from basstler_testing.recorded_pull_requests import RecordedPullRequestSource
from basstler_testing.plan.goal_path_fixtures import (
    GoalPlanId,
    StepId,
    GOAL,
    reference_of,
    recorded_pull_requests,
    path_with,
    step_of,
)
from basstler_testing.plan.goal_path_fixtures import plan_directory  # noqa: F401 - a fixture


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

    def test_the_next_step_is_the_first_one_something_moves_forward(
        self, plan_directory: PlanDirectory
    ):
        """
        The next step is the first of the sequence that a session or the owner can move.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert path.next_step == path.groups[0].steps[0]
        assert path.next_step.next_move is not None

    def test_the_sequence_numbers_every_unfinished_step_in_group_order(
        self, plan_directory: PlanDirectory
    ):
        """
        Every unfinished step has its place in the sequence, counted from one.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        in_group_order = [step for group in path.groups for step in group.steps]

        assert list(path.sequence) == in_group_order
        assert [path.position_of(step) for step in in_group_order] == list(
            range(1, len(in_group_order) + 1)
        )


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

    def test_the_text_names_the_next_step_s_move(self, plan_directory: PlanDirectory):
        """
        The printed path's second line gives the next move.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert path.next_step.next_move in path.render().splitlines()[1]

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

        assert step.owner_move == PullRequestMove(
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

        assert step.owner_move == PullRequestMove(
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


class TestWhoseTurnAStepIs:
    """
    A step under way is its owner's to review unless something is left for a session.
    """

    def test_a_draft_with_nothing_left_for_a_session_is_the_owners_to_review(
        self, plan_directory: PlanDirectory
    ):
        """
        A draft with passing checks and no recorded blocker waits on its owner's review.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        step = step_of(path, reference_of(StepId.IN_PROGRESS))

        assert step.is_owners_turn
        assert not step.needs_a_session
        assert step.next_move == OWNER_PREFIX + step.owner_move.description

    def test_a_recorded_blocker_on_an_in_progress_draft_leaves_it_to_its_owner(
        self, plan_directory: PlanDirectory
    ):
        """
        A blocker is shown, not read: an in-progress draft with passing checks waits on its
        owner's review whatever its blockers say.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        step = step_of(path, reference_of(StepId.IN_PROGRESS_WITH_BLOCKER))

        assert step.item.blockers
        assert not step.needs_a_session
        assert step.is_owners_turn
        assert step.next_move == OWNER_PREFIX + step.owner_move.description

    def test_failed_checks_leave_the_step_to_a_session(
        self, plan_directory: PlanDirectory
    ):
        """
        A draft whose checks failed is resolved by a session first.
        """
        path = path_with(
            plan_directory,
            recorded_pull_requests(
                draft=True, failing_items=frozenset({StepId.IN_PROGRESS})
            ),
        )
        step = step_of(path, reference_of(StepId.IN_PROGRESS))

        assert step.needs_a_session
        assert step.next_move == step.action.command

    def test_a_step_ready_to_start_is_a_sessions(self, plan_directory: PlanDirectory):
        """
        A not-started step whose dependencies are ready is started by a session.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=False))
        step = step_of(path, reference_of(StepId.NOT_STARTED_BEHIND_DRAFTS))

        assert step.needs_a_session
        assert step.next_move == step.action.command

    def test_a_merge_waiting_for_another_merge_moves_nothing_now(
        self, plan_directory: PlanDirectory
    ):
        """
        A ready pull request held back by an unmerged dependency has no move now.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=False))
        step = step_of(path, reference_of(StepId.STACKED_WITH_PULL_REQUEST))

        assert step.owner_move.after
        assert step.next_move is None

    def test_only_the_steps_that_are_the_owners_turn_wait_on_the_owner(
        self, plan_directory: PlanDirectory
    ):
        """
        The steps listed as the owner's are exactly those whose turn is the owner's.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))

        assert path.owner_steps == tuple(
            step for step in path.steps if step.is_owners_turn
        )

    def test_the_report_numbers_each_step_and_names_its_move(
        self, plan_directory: PlanDirectory
    ):
        """
        A reported step carries its place in the sequence and what moves it now.
        """
        path = path_with(plan_directory, recorded_pull_requests(draft=True))
        reported = [step for group in path.report().groups for step in group.steps]

        assert [(step.position, step.next_move) for step in reported] == [
            (path.position_of(step), step.next_move) for step in path.sequence
        ]


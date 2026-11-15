"""
The ``basstler goal`` commands: saving a goal and printing the path to it.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from basstler.exit_codes import ExitCode
from basstler.github.pull_request_source import (
    GitHubPullRequestSource,
    PullRequestSource,
)
from basstler.plan.goal import Goal, GoalStore
from basstler.plan.dependencies import DependencyReference, PlanDirectory
from basstler.plan.done_check import BasstlerCommandRunner, DoneChecker, FinishedStep
from basstler.plan.exceptions import StepReferenceWithoutPlanError
from basstler.plan.goal_path import GoalCommandName, GoalPath, NeededItems
from basstler.plan.item_bootstrap.documents import ProjectCheckout
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""


class GoalExitCode(ExitCode):
    """
    What a ``basstler goal`` command's exit status tells its caller.
    """

    SUCCESS = 0
    """
    The command did what it was asked.
    """

    NOTHING_TO_ACT_ON = 1
    """
    No step of the goal's path can be acted on now.
    """

    STEP_NOT_DONE = 2
    """
    A step's done check ran and did not pass.
    """


goal_app = App(
    name=GoalCommandName.GROUP,
    help="Save a goal and print the ordered path of plan items that reaches it.",
)
"""
The ``goal`` command group.
"""


def read_path(
    identifier: str, project_root: Path, pull_request_source: PullRequestSource
) -> GoalPath:
    """
    :param identifier: The goal's id.
    :param project_root: The repository whose notes branch holds the goal and the plans.
    :param pull_request_source: Where the items' live state is read from.
    :raises UnknownGoalError: If the notes branch holds no such goal.
    :raises UnresolvedGoalReferenceError: If the path reaches a reference naming no item.
    :return: The goal's path over the freshly fetched plans.
    """
    goal = GoalStore.from_project_root(project_root).read(identifier)
    with tempfile.TemporaryDirectory() as scratch:
        plan_directory = ProjectCheckout(project_root).check_out_manifests(
            Path(scratch)
        )
        return GoalPath.compute(goal, plan_directory, pull_request_source)


@goal_app.command(name=GoalCommandName.PATH)
def print_path(
    identifier: str,
    as_json: Annotated[bool, Parameter(name="--json")] = False,
) -> GoalExitCode:
    """
    Print every step between the plans as they stand and the goal, in order.

    :param identifier: The goal's id.
    :param as_json: Print the path as JSON instead of text.
    """
    path = read_path(identifier, Path.cwd(), GitHubPullRequestSource.from_environment())
    logger.info(
        json.dumps(path.report().to_json(), indent=2) if as_json else path.render()
    )
    return GoalExitCode.SUCCESS


def summary_lines(
    goals: list[Goal],
    plan_directory: PlanDirectory,
    pull_request_source: PullRequestSource,
) -> list[str]:
    """
    :param goals: The goals to summarize.
    :param plan_directory: The plans their targets and dependencies live in.
    :param pull_request_source: Where the items' live state is read from.
    :return: One line per goal: its progress and next command, or the reference that
        keeps its path from being computed.
    """
    lines = []
    for goal in goals:
        needed = NeededItems.of_goal(goal, plan_directory)
        if needed.unresolved:
            lines.append(
                f"{goal.identifier}: no path - {needed.unresolved[0].error_message()}"
            )
            continue
        lines.append(
            GoalPath.from_needed_items(needed, pull_request_source).summary_line
        )
    return lines


@goal_app.command(name=GoalCommandName.SUMMARY)
def print_summary() -> GoalExitCode:
    """
    Print one line per goal on the notes branch: how far it is and what comes next.
    """
    store = GoalStore.from_project_root(Path.cwd())
    store.branch.fetch()
    goals = [store.fetched_goal(known) for known in store.fetched_identifiers()]
    with tempfile.TemporaryDirectory() as scratch:
        plan_directory = ProjectCheckout(Path.cwd()).check_out_manifests(Path(scratch))
        lines = summary_lines(
            goals, plan_directory, GitHubPullRequestSource.from_environment()
        )
    logger.info("\n".join(lines))
    return GoalExitCode.SUCCESS


@goal_app.command(name=GoalCommandName.NEXT)
def print_next_step(identifier: str) -> GoalExitCode:
    """
    Print what moves the first step of the goal's path that can be acted on now.

    :param identifier: The goal's id.
    """
    next_step = read_path(
        identifier, Path.cwd(), GitHubPullRequestSource.from_environment()
    ).next_step
    if next_step is None:
        logger.info(f"No step of goal {identifier} can be acted on now.")
        return GoalExitCode.NOTHING_TO_ACT_ON
    logger.info(next_step.next_move)
    return GoalExitCode.SUCCESS


@goal_app.command(name=GoalCommandName.SET)
def set_goal(
    identifier: str,
    title: str,
    target: Annotated[list[str], Parameter(name="--target", negative=())],
) -> GoalExitCode:
    """
    Save a goal, in place of any with its id, once every target names a plan item.

    :param identifier: The goal's short name.
    :param title: The outcome, as a sentence that is true once the goal is reached.
    :param target: An item that reaches the outcome, as ``<plan-id>/<item-id>``; repeat
        for several.
    """
    goal = Goal(identifier=identifier, title=title, targets=target)
    store = GoalStore.from_project_root(Path.cwd())
    store.branch.fetch()
    with tempfile.TemporaryDirectory() as scratch:
        plan_directory = ProjectCheckout(Path.cwd()).check_out_manifests(Path(scratch))
        NeededItems.of_goal(goal, plan_directory).refuse_unresolved_references()
    store.write(goal)
    return GoalExitCode.SUCCESS


def check_steps(path: GoalPath, checker: DoneChecker) -> GoalExitCode:
    """
    Run every pending done check of the path and record the steps that pass as done.

    :param path: The goal's path.
    :param checker: What runs the checks.
    :return: Whether every check that ran passed.
    """
    outcomes = checker.outcomes_of(path)
    for outcome in outcomes:
        logger.info(outcome.description)
        if outcome.passed:
            FinishedStep(outcome.reference).record(checker.runner.project_root)
    if not outcomes:
        logger.info(f"No step of goal {path.goal.identifier} has a check to run now.")
    if all(outcome.passed for outcome in outcomes):
        return GoalExitCode.SUCCESS
    return GoalExitCode.STEP_NOT_DONE


@goal_app.command(name=GoalCommandName.CHECK)
def check_goal(identifier: str) -> GoalExitCode:
    """
    Run the done check of each step that has one and waits for nothing, and record the
    steps whose check passes as done.

    :param identifier: The goal's id.
    """
    path = read_path(identifier, Path.cwd(), GitHubPullRequestSource.from_environment())
    return check_steps(path, DoneChecker(BasstlerCommandRunner(Path.cwd())))


@goal_app.command(name=GoalCommandName.MARK_DONE)
def mark_done(step: str) -> GoalExitCode:
    """
    Record a step as done on its owner's word.

    :param step: The step's item, as ``<plan-id>/<item-id>``.
    """
    reference = DependencyReference.from_text(step)
    if not reference.is_well_formed or not reference.names_another_plan:
        raise StepReferenceWithoutPlanError(step)
    FinishedStep(reference).record(Path.cwd())
    return GoalExitCode.SUCCESS

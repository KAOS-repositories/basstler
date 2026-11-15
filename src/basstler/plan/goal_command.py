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
from basstler.plan.goal_path import GoalPath, NeededItems
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


goal_app = App(
    name="goal",
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


@goal_app.command(name="path")
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


@goal_app.command(name="next")
def print_next_step(identifier: str) -> GoalExitCode:
    """
    Print the command of the first step of the goal's path that can be acted on now.

    :param identifier: The goal's id.
    """
    next_step = read_path(
        identifier, Path.cwd(), GitHubPullRequestSource.from_environment()
    ).next_step
    if next_step is None:
        logger.info(f"No step of goal {identifier} can be acted on now.")
        return GoalExitCode.NOTHING_TO_ACT_ON
    logger.info(next_step.action.command)
    return GoalExitCode.SUCCESS


@goal_app.command(name="set")
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

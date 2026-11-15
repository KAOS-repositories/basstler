"""
Done checks: the basstler command an item names as proof it is done, run for the steps
of a goal's path and recorded on the plan when it succeeds.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from basstler.plan.dependencies import DependencyReference
from basstler.plan.goal_path import GoalPath
from basstler.plan.item_bootstrap.update import ItemUpdateRequest
from basstler.plan.model import ItemStatus, ManifestKey

# %% running a basstler command


@dataclass(frozen=True)
class BasstlerCommandRunner:
    """
    Runs basstler commands in a project and reports how each exits.
    """

    project_root: Path
    """
    The repository the commands run in.
    """

    def exit_status_of(self, arguments: list[str]) -> int:
        """
        :param arguments: What follows ``basstler`` on the command line.
        :return: The command's exit status.
        """
        return subprocess.run(
            [sys.executable, "-m", "basstler", *arguments],
            cwd=self.project_root,
            check=False,
        ).returncode


# %% recording a step as done


@dataclass(frozen=True)
class FinishedStep:
    """
    A step that has been carried out and is to be recorded as done on its plan.
    """

    reference: DependencyReference
    """
    The step's item, named with its plan.
    """

    def record(self, project_root: Path) -> None:
        """
        Set the item to done on its plan and push it.

        :param project_root: The repository whose notes branch holds the plan.
        :raises UnknownPlanError: If the plan has no manifest on the notes branch.
        :raises UnknownItemError: If the plan tracks no item of that id.
        """
        ItemUpdateRequest(
            plan_identifier=self.reference.plan_id,
            item_identifier=self.reference.item_identifier,
            values_by_key={ManifestKey.STATUS: ItemStatus.DONE},
        ).update(project_root)


# %% checking the steps of a path


@dataclass(frozen=True)
class DoneCheckOutcome:
    """
    How one step's done check exited.
    """

    reference: DependencyReference
    """
    The step's item, named with its plan.
    """

    exit_status: int
    """
    The exit status of the item's done check.
    """

    @property
    def passed(self) -> bool:
        """
        Whether the check proved the step done.
        """
        return self.exit_status == 0

    @property
    def description(self) -> str:
        """
        The outcome as one printed line.
        """
        if self.passed:
            return f"{self.reference.text}: done"
        return (
            f"{self.reference.text}: not done yet (its check exited {self.exit_status})"
        )


@dataclass(frozen=True)
class DoneChecker:
    """
    Runs the done check of every step of a path that one can decide now.
    """

    runner: BasstlerCommandRunner
    """
    What runs each check.
    """

    def outcomes_of(self, path: GoalPath) -> list[DoneCheckOutcome]:
        """
        :param path: A goal's path.
        :return: How the check of each step with a pending done check exited, in path
            order.
        """
        return [
            DoneCheckOutcome(
                step.reference, self.runner.exit_status_of(step.item.done_when)
            )
            for step in path.steps
            if step.has_pending_done_check
        ]

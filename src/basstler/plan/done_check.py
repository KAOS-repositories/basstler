"""
Done checks: the basstler command an item names as proof it is done, run for the steps
of a goal's path and recorded on the plan when it succeeds.
"""

from __future__ import annotations

import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


# %% recording what a step reached


@dataclass(frozen=True)
class StepRecord(ABC):
    """
    Something a step has reached, to be recorded on its item.
    """

    reference: DependencyReference
    """
    The step's item, named with its plan.
    """

    @property
    @abstractmethod
    def values_by_key(self) -> dict[ManifestKey, Any]:
        """
        The fields this record sets on the item.
        """

    def record(self, project_root: Path) -> None:
        """
        Set the fields on the item's plan and push it.

        :param project_root: The repository whose notes branch holds the plan.
        :raises UnknownPlanError: If the plan has no manifest on the notes branch.
        :raises UnknownItemError: If the plan tracks no item of that id.
        """
        ItemUpdateRequest(
            plan_identifier=self.reference.plan_id,
            item_identifier=self.reference.item_identifier,
            values_by_key=self.values_by_key,
        ).update(project_root)


@dataclass(frozen=True)
class FinishedStep(StepRecord):
    """
    A step that has been carried out and is to be recorded as done on its plan.
    """

    @property
    def values_by_key(self) -> dict[ManifestKey, Any]:
        return {ManifestKey.STATUS: ItemStatus.DONE}


@dataclass(frozen=True)
class FinishedPushes(StepRecord):
    """
    A step whose pull request takes no more pushes after one commit.
    """

    commit: str
    """
    The full id of the commit the item's pushes ended at.
    """

    @property
    def values_by_key(self) -> dict[ManifestKey, Any]:
        return {ManifestKey.PUSHES_DONE_AT: self.commit}


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

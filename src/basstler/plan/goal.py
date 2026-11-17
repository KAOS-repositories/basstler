"""
A goal: an outcome named by the plan items that reach it, kept on the notes branch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated

import pydantic
import yaml

from basstler.git.commands import GitCommandRunner
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ProjectLocation
from basstler.personal_notes.branch import (
    NotesBranchWriter,
    NotesFileChanges,
    NotesWriteOutcome,
    PersonalNotesBranch,
    PersonalNotesLocation,
)
from basstler.plan.dependencies import DependencyReference
from basstler.plan.exceptions import UnknownGoalError
from basstler.shell_configuration import FetchedBranchReference

# %% the goal


class Goal(ValidatedJSONModel):
    """
    An outcome and the items whose completion reaches it.

    Only the targets are stored; what they need is read from the plans.
    """

    identifier: Annotated[str, pydantic.Field(alias="id")]
    """
    The goal's short name, which is also its file's name.
    """

    title: str
    """
    The outcome, as a sentence that is true once the goal is reached.
    """

    targets: list[str]
    """
    The items that reach the outcome, each as ``<plan-id>/<item-id>``.
    """

    @pydantic.field_validator("targets")
    @classmethod
    def refuse_target_without_plan(cls, targets: list[str]) -> list[str]:
        """
        :param targets: The targets as read.
        :raises ValueError: If one is not ``<plan-id>/<item-id>``, or there are none.
        :return: The same targets.
        """
        malformed = [
            target
            for target in targets
            if not (reference := DependencyReference.from_text(target)).is_well_formed
            or not reference.names_another_plan
        ]
        if malformed or not targets:
            raise ValueError(
                "a goal needs at least one target, each <plan-id>/<item-id>; got "
                + (", ".join(malformed) or "none")
            )
        return targets

    @classmethod
    def from_yaml(cls, text: str) -> Goal:
        """
        :param text: A goal file's YAML.
        :raises pydantic.ValidationError: If the YAML does not hold a valid goal.
        :return: The goal it holds.
        """
        return cls.from_json(yaml.safe_load(text) or {})

    @staticmethod
    def files_in(plans_directory: Path) -> list[Path]:
        """
        :param plans_directory: A checked-out plans directory.
        :return: The goal files under its goals directory, in file-name order.
        """
        return sorted(
            (plans_directory / ProjectLocation.PLAN_GOALS.name).glob("*.yaml")
        )

    @classmethod
    def every_goal_in(cls, plans_directory: Path) -> list[Goal]:
        """
        :param plans_directory: A checked-out plans directory.
        :raises pydantic.ValidationError: If a goal file does not hold a valid goal.
        :return: The goals under its goals directory, in file-name order.
        """
        return [
            cls.from_yaml(path.read_text()) for path in cls.files_in(plans_directory)
        ]

    @property
    def target_references(self) -> list[DependencyReference]:
        """
        :attr:`targets`, parsed.
        """
        return [DependencyReference.from_text(target) for target in self.targets]

    def render(self) -> str:
        """
        :return: The goal file's YAML.
        """
        return yaml.safe_dump(
            self.to_json(), sort_keys=False, allow_unicode=True, width=92
        )


# %% goals on the notes branch


@dataclass(frozen=True)
class GoalStore:
    """
    Reads and writes one repository's goals on its notes branch.
    """

    branch: PersonalNotesBranch
    """
    The notes branch holding the goals.
    """

    @classmethod
    def from_project_root(cls, project_root: Path) -> GoalStore:
        """
        :param project_root: The clone whose settings say where the notes are.
        :return: The store over that clone's notes branch.
        """
        return cls(
            PersonalNotesBranch(
                location=PersonalNotesLocation.resolve(project_root, os.environ),
                git=GitCommandRunner(project_root),
            )
        )

    @staticmethod
    def goal_path(identifier: str) -> PurePosixPath:
        """
        :param identifier: A goal's id.
        :return: That goal's file, relative to the notes branch's root.
        """
        return PurePosixPath(ProjectLocation.PLAN_GOALS) / f"{identifier}.yaml"

    def fetched_identifiers(self) -> tuple[str, ...]:
        """
        :return: The ids of the goals on the notes branch as last fetched, sorted.
        """
        listing = self.branch.git.attempt(
            "ls-tree",
            "--name-only",
            FetchedBranchReference.PERSONAL_NOTES.file_at(
                PurePosixPath(ProjectLocation.PLAN_GOALS)
            )
            + "/",
        )
        if not listing.succeeded:
            return ()
        return tuple(
            sorted(PurePosixPath(name).stem for name in listing.output.splitlines())
        )

    def read(self, identifier: str) -> Goal:
        """
        Fetch the notes branch, then read one goal.

        :param identifier: The goal's id.
        :raises NotesBranchMissingError: If no remote has the notes branch.
        :raises UnknownGoalError: If the notes branch holds no such goal.
        :return: The goal.
        """
        self.branch.fetch()
        known = self.fetched_identifiers()
        if identifier not in known:
            raise UnknownGoalError(identifier, known)
        return self.fetched_goal(identifier)

    def fetched_goal(self, identifier: str) -> Goal:
        """
        :param identifier: The id of a goal the notes branch held when last fetched.
        :return: That goal.
        """
        return Goal.from_yaml(
            self.branch.git.run(
                "show",
                FetchedBranchReference.PERSONAL_NOTES.file_at(
                    self.goal_path(identifier)
                ),
            )
        )

    def write(self, goal: Goal) -> NotesWriteOutcome:
        """
        Put the goal on the notes branch, in place of any with its id, and push it.

        :param goal: The goal the branch is to hold.
        :return: Whether anything was pushed.
        """
        return NotesBranchWriter(self.branch).write(
            NotesFileChanges({self.goal_path(goal.identifier): goal.render()}),
            f"Set goal {goal.identifier}",
        )

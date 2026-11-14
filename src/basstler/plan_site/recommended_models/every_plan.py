"""
Filling in the missing recommended models of every plan on a notes branch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from basstler.git.commands import GitCommandRunner
from basstler.locations import ProjectLocation
from basstler.personal_notes.branch import (
    NotesBranchWriter,
    NotesEdit,
    PersonalNotesBranch,
    PersonalNotesLocation,
)
from basstler.plan.model import PlanDocument, PlanManifest
from basstler.plan.model_alias import ModelAlias

# %% every plan on a notes branch


class RecommendedModelsCommand(StrEnum):
    """
    The subcommands this command answers.
    """

    EVERY_PLAN = "every-plan"
    """
    Fill the missing recommended models of every plan on the notes branch, and push them.
    """


class RecommendedModelsLine(StrEnum):
    """
    The line that says what filling every plan's recommended models did.
    """

    NONE = "none - every item of every plan has one"
    """
    No plan had an item without a recommended model.
    """

    FILLED = "filled in the plans: {plans}"
    """
    Names every plan that had an item without one.
    """


@dataclass
class RecommendedModelsSummary:
    """
    What filling every plan's recommended models did.
    """

    filled_plans: list[str] = field(default_factory=list)
    """
    The directory names of the plans that had an item without a recommended model.
    """

    @property
    def line(self) -> str:
        """
        :return: The summary in one line.
        """
        if not self.filled_plans:
            return RecommendedModelsLine.NONE.value
        return RecommendedModelsLine.FILLED.format(plans=", ".join(self.filled_plans))


@dataclass
class RecommendedModelsInEveryPlan(NotesEdit):
    """
    Gives every item of every plan that has no recommended model the *fallback*.
    """

    fallback: ModelAlias = ModelAlias.SONNET
    """
    The model an item gets when nothing says which suits its difficulty.
    """

    summary: RecommendedModelsSummary = field(default_factory=RecommendedModelsSummary)
    """
    What the latest :meth:`apply` did.
    """

    def apply(self, root: Path) -> None:
        self.summary = RecommendedModelsSummary()
        plans_root = root / ProjectLocation.PLANS
        for manifest_path in sorted(plans_root.glob(f"*/{PlanDocument.MANIFEST}")):
            manifest = PlanManifest.from_file(manifest_path)
            filled = manifest.with_recommended_models(self.fallback)
            if filled == manifest:
                continue
            filled.write(manifest_path)
            self.summary.filled_plans.append(manifest_path.parent.name)

    def record_on_notes_branch(self, project_root: Path, *, push_attempts: int) -> str:
        """
        Apply this edit to the latest notes branch of *project_root* and push it.

        :param project_root: The clone whose settings say where the notes are.
        :param push_attempts: How many pushes to make before giving up on a branch that
            keeps moving.
        :raises NotesPushRejectedError: If every push was rejected.
        :return: The line saying what was filled in.
        """
        branch = PersonalNotesBranch(
            location=PersonalNotesLocation.resolve(project_root, os.environ),
            git=GitCommandRunner(project_root),
        )
        NotesBranchWriter(branch, push_attempts).write(
            self, "Fill in the recommended models of plan items"
        )
        return self.summary.line

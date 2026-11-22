"""
The plans, goals and pull requests test_done_check.py and the plan site's goal page tests share.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import PurePosixPath
import pytest
from basstler.locations import PluginLocation, ProjectLocation
from basstler.plan.dependencies import PlanDirectory
from basstler.plan.done_check import (
    BasstlerCommandRunner,
)
from basstler.plan.model import PlanDocument, PlanManifest
from basstler_testing.constants.paths import DatasetLocation
from basstler_testing.scratch_repository import ScratchRepository
from basstler_testing.plan.owner_steps_fixtures import PLAN_ID, StepId


@dataclass(frozen=True)
class RecordedExitStatus(BasstlerCommandRunner):
    """
    Answers every command with one fixed exit status, noting what it was asked to run.
    """

    exit_status: int = 0
    """
    The status every command exits with.
    """

    commands_run: list[list[str]] = field(default_factory=list)
    """
    The arguments of every command asked for, in order.
    """

    def exit_status_of(self, arguments: list[str]) -> int:
        self.commands_run.append(arguments)
        return self.exit_status


@pytest.fixture
def plan_directory() -> PlanDirectory:
    """
    :return: The plan whose owner's step carries a done check, read afresh.
    """
    return PlanDirectory(DatasetLocation.OWNER_STEP_PLANS)


@pytest.fixture
def owner_step_repository(
    scratch_repository: ScratchRepository, monkeypatch: pytest.MonkeyPatch
) -> ScratchRepository:
    """
    :return: A scratch repository, entered, whose notes branch carries the plan.
    """
    scratch_repository.install_hook_scripts(
        PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT.name,
        PluginLocation.PLAN_SAVING_SCRIPT.name,
    )
    scratch_repository.install_package()
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch(
        {
            ProjectLocation.PLANS
            / file.relative_to(DatasetLocation.OWNER_STEP_PLANS): file.read_text(encoding="utf-8")
            for file in sorted(DatasetLocation.OWNER_STEP_PLANS.rglob("*"))
            if file.is_file()
        }
    )
    scratch_repository.resolve_notes_remote_to()
    scratch_repository.serve_origin_as(
        PlanManifest.from_file(
            DatasetLocation.OWNER_STEP_PLANS / PLAN_ID / PlanDocument.MANIFEST
        ).default_repository
    )
    monkeypatch.chdir(scratch_repository.project_root)
    return scratch_repository


def published_manifest(repository: ScratchRepository) -> PlanManifest:
    """
    :return: The plan as the notes remote holds it.
    """
    return PlanManifest.from_yaml(
        repository.published_file(PurePosixPath(PlanDocument.MANIFEST.path_within_notes_branch(PLAN_ID)),
        )
    )


def is_recorded_done(repository: ScratchRepository, step: StepId) -> bool:
    """
    :return: Whether the notes remote counts the step's item as landed, which a save
        does by dropping it from the plan.
    """
    manifest = published_manifest(repository)
    remaining = {item.identifier for item in manifest.items}
    return step not in remaining and manifest.landed_item_count == 1


"""
The plan handover the handover tests hand over, and the repositories they hand it
between.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import pytest

from basstler.github.repository import Repository
from basstler.locations import PlanHandoverLocation, PluginLocation, ProjectLocation
from basstler.plan.handover import PlanHandover
from basstler.plan.merged_items import __main__ as merged_items_command
from basstler.plan.model import PlanDocument, PlanManifest
from basstler.plan_site import build_start

from ..constants.paths import DatasetLocation
from ..scratch_repository import ScratchRepository

# %% the dataset handover


class HandedOverPlan(StrEnum):
    """
    The ids of the plans :attr:`DatasetLocation.HANDOVER` holds.
    """

    UPSTREAM = "upstream-work"
    """
    The plan whose item the other plan depends on.
    """

    DOWNSTREAM = "downstream-work"
    """
    The plan depending on an item of :attr:`UPSTREAM`.
    """


UNRELATED_BRANCH = "unrelated-branch"
"""
The branch of :attr:`DatasetLocation.UNRELATED_PROGRESS_NOTE`, which no handed-over plan
tracks.
"""

RECEIVERS_FORK = Repository("receiver", "repo")
"""
The receiver's own fork, which the dataset's plans are not on.
"""


def plans_repository() -> Repository:
    """
    :return: The repository the dataset's plans are on.
    """
    return PlanManifest.from_file(
        DatasetLocation.HANDOVER
        / PlanHandoverLocation.PLANS
        / HandedOverPlan.UPSTREAM
        / PlanDocument.MANIFEST
    ).default_repository


@pytest.fixture
def dataset_handover() -> PlanHandover:
    """
    :return: The handover the dataset holds.
    """
    return PlanHandover.from_directory(DatasetLocation.HANDOVER.value)


# %% the repositories


def notes_branch_files(handover: PlanHandover) -> dict[Path, str]:
    """
    :param handover: A handover.
    :return: Its plans, progress notes and rules at the paths a notes branch holds them.
    """
    files = {
        ProjectLocation.PULL_REQUEST_PROGRESS
        / handover.progress_note_path(branch): note
        for branch, note in handover.progress_notes.items()
    }
    for plan in handover.plans:
        for document, text in (
            (PlanDocument.MANIFEST, plan.manifest.text),
            (PlanDocument.ROADMAP, plan.roadmap_text),
        ):
            files[Path(document.path_within_notes_branch(plan.identifier))] = text
    files[ProjectLocation.PLAN_RULES] = handover.repository_rules.render()
    return files


def handover_repository(
    repository: ScratchRepository, notes: dict[Path, str], origin: Repository
) -> ScratchRepository:
    """
    Set *repository* up as a clone of *origin* whose default branch is published, with
    *notes* on its notes branch, and stand-ins for the plan site build and the
    merged-item lookup.

    :param repository: The initialized scratch repository and notes remote.
    :param notes: The files its notes branch is to hold.
    :param origin: The repository its ``origin`` names.
    :return: The same repository.
    """
    repository.install_hook_scripts(
        PluginLocation.PERSONAL_NOTES_CONFIGURATION_SCRIPT.name,
        PluginLocation.PLAN_SAVING_SCRIPT.name,
    )
    repository.install_package()
    repository.replace_package_module(build_start, DatasetLocation.BUILD_START_STUB)
    repository.replace_package_module(
        merged_items_command, DatasetLocation.MERGED_ITEMS_STUB
    )
    repository.write("README.md", "scratch repo\n")
    repository.commit_everything("initial commit")
    repository.publish_notes_branch(notes)
    repository.resolve_notes_remote_to()
    repository.serve_origin_as(origin)
    repository.run_git("push", "--quiet", "origin", "HEAD:refs/heads/main")
    return repository


@pytest.fixture
def exporting_repository(
    scratch_repository: ScratchRepository, dataset_handover: PlanHandover
) -> ScratchRepository:
    """
    :return: A clone of the plans' repository whose notes branch holds the dataset's
        plans, the progress notes of their branches and of one branch they do not
        track, and the rules.
    """
    notes = notes_branch_files(dataset_handover)
    notes[
        ProjectLocation.PULL_REQUEST_PROGRESS
        / PlanHandover.progress_note_path(UNRELATED_BRANCH)
    ] = DatasetLocation.UNRELATED_PROGRESS_NOTE.read_text(encoding="utf-8")
    return handover_repository(scratch_repository, notes, plans_repository())


@pytest.fixture
def receiving_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    :return: A clone of the plans' repository whose notes branch holds no plan.
    """
    return handover_repository(
        scratch_repository,
        {ProjectLocation.PERSONAL_NOTES_DOCUMENT: "notes\n"},
        plans_repository(),
    )


@pytest.fixture
def receivers_fork(tmp_path: Path) -> ScratchRepository:
    """
    :return: A clone of :data:`RECEIVERS_FORK`, beside the scratch repository, whose
        notes branch holds no plan.
    """
    return handover_repository(
        ScratchRepository.create(tmp_path / "receiver"),
        {ProjectLocation.PERSONAL_NOTES_DOCUMENT: "notes\n"},
        RECEIVERS_FORK,
    )

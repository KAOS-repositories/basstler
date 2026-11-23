"""
Triaging an import respelled from a module re-exporting a member to the module that
defines it.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.comparison import MechanicalChange
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import ReexportedImportSample

# %% the sample


@pytest.fixture
def reexported_import(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample respelling imports of re-exported members, committed to a
        scratch repository.
    """
    return committed_pull_request(
        scratch_repository,
        ReexportedImportSample.BASE_TREE,
        ReexportedImportSample.HEAD_TREE,
    )


@pytest.fixture
def reexported_import_triage(reexported_import: PullRequestChanges) -> TriageOutcome:
    """
    :return: The triage of the sample.
    """
    return PullRequestTriager().triage(reexported_import)


# %% respelled imports


def test_an_import_respelled_to_the_module_a_reexport_reads_from_is_mechanical(
    reexported_import_triage: TriageOutcome,
):
    """
    ``from shapes.types import Point`` becoming ``from shapes.point import Point``,
    where the head's ``shapes.types`` imports ``Point`` from ``shapes.point``, binds the
    same class.
    """
    kinds = {
        file.change.path: file.kinds
        for file in reexported_import_triage.mechanical_files
    }
    assert kinds[PurePosixPath("caller.py")] == frozenset({MechanicalChange.IMPORTS})


def test_an_import_respelled_to_a_module_binding_another_object_needs_review(
    reexported_import_triage: TriageOutcome,
):
    """
    ``from shapes.types import Shape`` becoming ``from shapes.point import Shape``,
    where the head's ``shapes.types`` imports ``Shape`` from ``shapes.outline``, binds a
    different class.
    """
    assert PurePosixPath("other_caller.py") in {
        file.change.path for file in reexported_import_triage.files_needing_review
    }


def test_an_import_respelled_to_what_a_changed_reexport_binds_needs_review(
    reexported_import_triage: TriageOutcome,
):
    """
    ``from shapes.drawing import Shape`` becoming ``from shapes.point import Shape``,
    where ``shapes.drawing`` imports ``Shape`` from ``shapes.point`` only in the head,
    binds a different class than the base version did.
    """
    assert PurePosixPath("drawing_caller.py") in {
        file.change.path for file in reexported_import_triage.files_needing_review
    }

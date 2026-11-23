"""
Proving a rename of a class's method or attribute mechanical by resolving each
occurrence reached through ``self``, ``cls`` or the class itself to the attribute it
refers to.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.comparison import MechanicalChange
from basstler.review_triage.detection import MemberRenameDetection
from basstler.review_triage.renames import AttributeRename
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import AttributeRenameSample

# %% the sample


@pytest.fixture
def attribute_rename(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample renaming methods and attributes of classes, committed.
    """
    return committed_pull_request(
        scratch_repository,
        AttributeRenameSample.BASE_TREE,
        AttributeRenameSample.HEAD_TREE,
    )


@pytest.fixture
def attribute_rename_triage(attribute_rename: PullRequestChanges) -> TriageOutcome:
    """
    :return: The sample, triaged.
    """
    return PullRequestTriager().triage(attribute_rename)


# %% detection


def test_renamed_attributes_are_renames_of_their_qualified_paths(
    attribute_rename: PullRequestChanges,
):
    """
    A method or attribute a class defines under a new name is renamed by its class's
    qualified path; an override left behind or inherited from the standard library
    keeps its old name from being renamed.
    """
    decisions = MemberRenameDetection().decisions(attribute_rename)
    assert {
        (rename.old, rename.new)
        for rename in decisions.accepted
        if isinstance(rename, AttributeRename)
    } == {
        ("shapes.circle.Circle.perimeter", "shapes.circle.Circle.boundary_length"),
        (
            "shapes.scaled.ScaledVector.scaled_norm_squared",
            "shapes.scaled.ScaledVector.scaled_squared_length",
        ),
        ("shapes.shape.Shape.perimeter", "shapes.shape.Shape.boundary_length"),
        ("shapes.vector.Vector.norm_squared", "shapes.vector.Vector.squared_length"),
        ("shapes.vector.Vector.tag", "shapes.vector.Vector.caption"),
    }


# %% triage


def test_occurrences_bound_to_the_renamed_attributes_are_mechanical(
    attribute_rename_triage: TriageOutcome,
):
    """
    The defining classes, their methods through ``self`` and ``cls``, the class read by
    name, and a subclass using inherited attributes change only by the renames.
    """
    assert {
        file.change.path: file.kinds
        for file in attribute_rename_triage.mechanical_files
    } == dict.fromkeys(
        (
            PurePosixPath("shapes/circle.py"),
            PurePosixPath("shapes/scaled.py"),
            PurePosixPath("shapes/shape.py"),
            PurePosixPath("shapes/vector.py"),
        ),
        frozenset({MechanicalChange.RENAME}),
    )


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(PurePosixPath("app/receiver.py"), id="unresolved-receiver"),
        pytest.param(PurePosixPath("app/unrelated.py"), id="unrelated-class"),
        pytest.param(PurePosixPath("app/static.py"), id="static-method-parameter"),
        pytest.param(PurePosixPath("app/worker.py"), id="standard-library-override"),
        pytest.param(PurePosixPath("shapes/polygon.py"), id="override-left-behind"),
    ],
)
def test_an_attribute_not_bound_to_a_renamed_one_needs_review(
    attribute_rename_triage: TriageOutcome, path: PurePosixPath
):
    """
    An attribute of the old name that is not proven to be the renamed one, changed to
    the new name, leaves its file for review.
    """
    assert path in {
        file.change.path for file in attribute_rename_triage.files_needing_review
    }

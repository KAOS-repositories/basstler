"""
Pairing the top-level definitions a pull request removes with those it adds by how alike
their code is.
"""

from __future__ import annotations

import ast

from basstler.review_triage.definition_succession import (
    DefinitionCode,
    DefinitionSuccession,
)

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import DefinitionMoveAgainstRenameSample, DefinitionMoveAndRenameSample

# %% the closest match


def test_two_equally_close_candidates_leave_no_single_closest():
    """
    A tie between the closest candidates names neither.
    """
    assert DefinitionSuccession.single_closest({"first": 0.5, "second": 0.5}) is None


def test_a_candidate_alike_in_nothing_is_no_closest_match():
    """
    The only candidate is no match when nothing of it is alike.
    """
    assert DefinitionSuccession.single_closest({"only": 0.0}) is None


def test_the_most_alike_candidate_is_the_single_closest():
    """
    The candidate more alike than every other is the closest.
    """
    assert DefinitionSuccession.single_closest({"near": 0.9, "far": 0.4}) == "near"


def test_definitions_of_different_kinds_are_alike_in_nothing():
    """
    A class and a function share no likeness, even with the same lines.
    """
    lines = ("pass",)
    assert (
        DefinitionCode(ast.ClassDef, lines).likeness(
            DefinitionCode(ast.FunctionDef, lines)
        )
        == 0.0
    )


# %% successors in a pull request


def test_a_definition_moved_under_a_new_name_succeeds_its_old_one(
    scratch_repository: ScratchRepository,
):
    """
    The class added in another module under another name carries on the removed one.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMoveAndRenameSample.BASE_TREE,
        DefinitionMoveAndRenameSample.HEAD_TREE,
    )
    assert DefinitionSuccession.from_changes(changes).successors == {
        "package.shapes.Square": "package.polygons.RegularSquare"
    }


def test_a_new_namesake_does_not_succeed_a_definition_renamed_in_place(
    scratch_repository: ScratchRepository,
):
    """
    A class renamed in its module carries it on, not a new class of its old name
    elsewhere, which is then contested.
    """
    changes = committed_pull_request(
        scratch_repository,
        DefinitionMoveAgainstRenameSample.BASE_TREE,
        DefinitionMoveAgainstRenameSample.HEAD_TREE,
    )
    succession = DefinitionSuccession.from_changes(changes)
    assert succession.successors == {
        "package.geometry.Pose": "package.geometry.Pose3Dimensional"
    }
    assert not succession.is_uncontested("package.geometry.Pose", "package.pose.Pose")

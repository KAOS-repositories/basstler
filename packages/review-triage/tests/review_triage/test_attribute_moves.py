"""
Detecting a class attribute moved into another class as a rename of its dotted path, and
triaging the files that read it from there.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.member_moves import AttributeMoveDetection
from basstler.review_triage.renames import (
    AttributeMove,
    ClassAttribute,
    ModuleMember,
    RenameDecisions,
)
from basstler.review_triage.triage import PullRequestTriager
from basstler.text_file import TextFile

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import commit_trees, pull_request_between
from .samples import AttributeMoveSample

# %% the sample

NEW_MODULE = Path("tool/setup_locations.py")
"""
The module the sample adds, holding the class the member moves into.
"""

DEFINING_MODULES = frozenset(
    {PurePosixPath("tool/locations.py"), PurePosixPath(NEW_MODULE)}
)
"""
The modules the member moves between, whose change a reviewer reads.
"""

READING_MODULES = frozenset(
    {PurePosixPath("tool/setup.py"), PurePosixPath("tool/scripts.py")}
)
"""
The modules reading the member from its new class.
"""

RE_EXPORTING_USER = Path("tool/hooks.py")
"""
Where the variant reading the old class from a module that stops importing it is put.
"""

OLD_MODULE = Path("tool/locations.py")
"""
The module the member leaves.
"""

FILE_NAME_READER = Path("tool/names.py")
"""
Where the variants reading the method only the old class has are put.
"""

OTHER_LOSER = Path("tool/release.py")
"""
Where the variant of a second class losing a member of the moved one's name is put.
"""

SAMPLE_MOVE = (
    "tool.locations.PluginLocation.SETUP_SCRIPT",
    "tool.setup_locations.SetupPluginLocation.SETUP_SCRIPT",
)
"""
The old and new dotted path of the member the sample moves.
"""

Variants = dict[Path, AttributeMoveSample]
"""
Variants of the sample's files, each in place of the file at its path.
"""


def attribute_move(
    scratch_repository: ScratchRepository,
    base_variants: Variants | None = None,
    head_variants: Variants | None = None,
) -> PullRequestChanges:
    """
    :param scratch_repository: The repository to commit in.
    :param base_variants: Variants of the base tree's files.
    :param head_variants: Variants of the head tree's files.
    :return: The sample, committed.
    """
    trees = []
    for tree, variants in (
        (AttributeMoveSample.BASE_TREE, base_variants),
        (AttributeMoveSample.HEAD_TREE, head_variants),
    ):
        files = tree.files()
        for path, variant in (variants or {}).items():
            files[path] = TextFile(variant.path).read()
        trees.append(files)
    return pull_request_between(commit_trees(scratch_repository, *trees))


def moved_paths(changes: PullRequestChanges) -> list[tuple[str, str]]:
    """
    :param changes: A pull request.
    :return: The old and new dotted path of each attribute it moves.
    """
    return [
        (move.old, move.new)
        for move in AttributeMoveDetection().decisions(changes).accepted
    ]


def needing_review(changes: PullRequestChanges) -> frozenset[PurePosixPath]:
    """
    :param changes: A pull request.
    :return: The files of it that need review.
    """
    return frozenset(
        file.change.path
        for file in PullRequestTriager().triage(changes).files_needing_review
    )


# %% detection


def test_a_member_moved_into_a_like_class_is_a_rename_of_its_path(
    scratch_repository: ScratchRepository,
):
    """
    The member keeps its name and its value, and the class it moves into has the old
    class's bases and methods.
    """
    detection = AttributeMoveDetection()
    assert detection.decisions(attribute_move(scratch_repository)) == (
        RenameDecisions(
            (
                AttributeMove(
                    "tool.locations.PluginLocation.SETUP_SCRIPT",
                    "tool.setup_locations.SetupPluginLocation.SETUP_SCRIPT",
                    detection,
                    attribute=ClassAttribute(
                        ModuleMember("tool.locations", "PluginLocation"), "SETUP_SCRIPT"
                    ),
                    new_owner=ModuleMember(
                        "tool.setup_locations", "SetupPluginLocation"
                    ),
                ),
            )
        )
    )


@pytest.mark.parametrize(
    "new_module",
    [
        AttributeMoveSample.OTHER_VALUE,
        AttributeMoveSample.OTHER_BASE,
        AttributeMoveSample.ADDED_METHOD,
    ],
)
def test_a_member_moved_into_an_unlike_class_is_no_rename(
    scratch_repository: ScratchRepository, new_module: AttributeMoveSample
):
    """
    A member given another value, or moved into a class of other bases or methods,
    behaves otherwise once read from its new class.
    """
    changes = attribute_move(scratch_repository, head_variants={NEW_MODULE: new_module})
    assert AttributeMoveDetection().decisions(changes) == RenameDecisions()


# %% triage


def test_the_modules_reading_a_moved_member_from_its_new_class_are_mechanical(
    scratch_repository: ScratchRepository,
):
    """
    Only the modules the member moves between need review.
    """
    assert needing_review(attribute_move(scratch_repository)) == DEFINING_MODULES


@pytest.mark.parametrize(
    "new_module",
    [
        AttributeMoveSample.OTHER_VALUE,
        AttributeMoveSample.OTHER_BASE,
        AttributeMoveSample.ADDED_METHOD,
    ],
)
def test_the_modules_reading_a_member_moved_into_an_unlike_class_need_review(
    scratch_repository: ScratchRepository, new_module: AttributeMoveSample
):
    """
    Each module reading the member reads something that may behave otherwise.
    """
    changes = attribute_move(scratch_repository, head_variants={NEW_MODULE: new_module})
    assert needing_review(changes) == DEFINING_MODULES | READING_MODULES


def test_dropping_the_import_another_module_reads_from_it_needs_review(
    scratch_repository: ScratchRepository,
):
    """
    A module that stops importing the old class, once it reads the member from the new
    one, needs review when another module imports the old class from it.
    """
    user = {RE_EXPORTING_USER: AttributeMoveSample.RE_EXPORTING_USER}
    changes = attribute_move(scratch_repository, user, user)
    assert PurePosixPath("tool/setup.py") in needing_review(changes)


# %% what the old class gives that the new one does not


def test_a_method_the_new_class_lacks_and_no_moved_member_reads_keeps_the_move(
    scratch_repository: ScratchRepository,
):
    """
    A method of the old class the new one lacks changes nothing for the moved member
    when the commit reads it from members that stay only.
    """
    changes = attribute_move(
        scratch_repository,
        {
            OLD_MODULE: AttributeMoveSample.LOCATIONS_WITH_METHOD_BASE,
            FILE_NAME_READER: AttributeMoveSample.UNMOVED_FILE_NAME_READER,
        },
        {
            OLD_MODULE: AttributeMoveSample.LOCATIONS_WITH_METHOD_HEAD,
            FILE_NAME_READER: AttributeMoveSample.UNMOVED_FILE_NAME_READER,
        },
    )
    assert moved_paths(changes) == [SAMPLE_MOVE]


def test_a_method_the_new_class_lacks_read_from_the_moved_member_is_no_move(
    scratch_repository: ScratchRepository,
):
    """
    The moved member no longer has a method the commit reads from it.
    """
    changes = attribute_move(
        scratch_repository,
        {
            OLD_MODULE: AttributeMoveSample.LOCATIONS_WITH_METHOD_BASE,
            FILE_NAME_READER: AttributeMoveSample.MOVED_FILE_NAME_READER_BASE,
        },
        {
            OLD_MODULE: AttributeMoveSample.LOCATIONS_WITH_METHOD_HEAD,
            FILE_NAME_READER: AttributeMoveSample.MOVED_FILE_NAME_READER_HEAD,
        },
    )
    assert moved_paths(changes) == []


# %% more than one class losing the name


def test_of_two_classes_losing_the_name_the_one_whose_member_moves_alike_is_moved(
    scratch_repository: ScratchRepository,
):
    """
    Another class dropping a member of the moved one's name, with another value, leaves
    the one move whose value and class match.
    """
    changes = attribute_move(
        scratch_repository,
        {OTHER_LOSER: AttributeMoveSample.OTHER_LOSER_BASE},
        {OTHER_LOSER: AttributeMoveSample.OTHER_LOSER_HEAD},
    )
    assert moved_paths(changes) == [SAMPLE_MOVE]

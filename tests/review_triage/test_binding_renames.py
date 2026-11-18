"""
Proving a rename of a module's class mechanical by resolving each occurrence of its old
name to the binding it refers to, never by its spelling.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.comparison import MechanicalChange
from basstler.review_triage.detection import MemberRenameDetection
from basstler.review_triage.renames import MemberRename, RenameDecisions
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

from ..scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import BindingRenameSample

# %% the sample


@pytest.fixture
def binding_rename(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample renaming ``geometry.spatial.Pose``, committed.
    """
    return committed_pull_request(
        scratch_repository,
        BindingRenameSample.BASE_TREE,
        BindingRenameSample.HEAD_TREE,
    )


@pytest.fixture
def binding_rename_triage(binding_rename: PullRequestChanges) -> TriageOutcome:
    """
    :return: The sample, triaged.
    """
    return PullRequestTriager().triage(binding_rename)


# %% detection


def test_a_renamed_module_member_is_a_rename_of_its_qualified_path(
    binding_rename: PullRequestChanges,
):
    """
    A class its module defines under a new name is renamed by its qualified path, even
    though an unrelated class keeps the old name.
    """
    assert MemberRenameDetection().decisions(binding_rename) == RenameDecisions(
        (
            MemberRename(
                "geometry.spatial.Pose",
                "geometry.spatial.Pose3Dimensional",
                MemberRenameDetection(),
            ),
        )
    )


# %% triage


def test_occurrences_bound_to_the_renamed_class_are_mechanical(
    binding_rename_triage: TriageOutcome,
):
    """
    The defining module, a re-export, aliased, module and fallback imports, imports
    after star imports not binding the name, a function's own class left alone, a
    docstring keeping the old word, qualified documentation references and code blocks
    or notebook cells using a class an earlier one imports change only by the rename.
    """
    assert {
        file.change.path: file.kinds for file in binding_rename_triage.mechanical_files
    } == dict.fromkeys(
        (
            PurePosixPath("README.md"),
            PurePosixPath("app/import_fallback.py"),
            PurePosixPath("app/module_alias.py"),
            PurePosixPath("app/planner.py"),
            PurePosixPath("app/prose_kept.py"),
            PurePosixPath("app/shadowed_kept.py"),
            PurePosixPath("app/star_imported.py"),
            PurePosixPath("app/star_imported_after_code.py"),
            PurePosixPath("app/star_imported_unrelated_last.py"),
            PurePosixPath("app/via_api.py"),
            PurePosixPath("docs/notebook.md"),
            PurePosixPath("docs/notebook_options.md"),
            PurePosixPath("docs/usage.md"),
            PurePosixPath("geometry/api.py"),
            PurePosixPath("geometry/spatial.py"),
        ),
        frozenset({MechanicalChange.RENAME}),
    )


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(PurePosixPath("app/robot_pose_swapped.py"), id="unrelated-class"),
        pytest.param(PurePosixPath("app/shadowed.py"), id="function-own-class"),
        pytest.param(PurePosixPath("app/ros.py"), id="external-class"),
        pytest.param(
            PurePosixPath("docs/ros_usage.md"), id="external-class-in-documentation"
        ),
        pytest.param(PurePosixPath("app/conditional.py"), id="ambiguous-binding"),
        pytest.param(
            PurePosixPath("app/star_imported_last.py"), id="star-import-after-binding"
        ),
        pytest.param(
            PurePosixPath("app/used_before_import.py"), id="used-before-binding"
        ),
        pytest.param(PurePosixPath("app/captured.py"), id="new-name-captured"),
        pytest.param(PurePosixPath("app/string_literal.py"), id="string-literal"),
        pytest.param(PurePosixPath("CHANGELOG.md"), id="unqualified-prose"),
    ],
)
def test_an_old_name_not_bound_to_the_renamed_class_needs_review(
    binding_rename_triage: TriageOutcome, path: PurePosixPath
):
    """
    A spelling of the old name that is not proven to refer to the renamed class, changed
    to the new name, leaves its file for review.
    """
    assert path in {
        file.change.path for file in binding_rename_triage.files_needing_review
    }

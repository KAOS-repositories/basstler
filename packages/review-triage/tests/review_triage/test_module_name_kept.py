"""
Triaging an import respelled to another module while the module it imported from stays.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.detection import RenameDetection
from basstler.review_triage.renames import RenameDecisions
from basstler.review_triage.triage import PullRequestTriager

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import ModuleNameKeptSample

# %% the sample


@pytest.fixture
def module_name_kept(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The pull request respelling an import to another module, while the module
        it imported from stays.
    """
    return committed_pull_request(
        scratch_repository,
        ModuleNameKeptSample.BASE_TREE,
        ModuleNameKeptSample.HEAD_TREE,
    )


# %% the module name is no rename


def test_a_module_name_kept_as_a_file_of_the_head_is_no_rename(
    module_name_kept: PullRequestChanges,
):
    """
    A module name the diff replaces is no rename while a file of the head still has it.
    """
    assert RenameDetection().decisions(module_name_kept) == RenameDecisions(())


def test_an_import_respelled_to_another_module_that_still_exists_needs_review(
    module_name_kept: PullRequestChanges,
):
    """
    An import respelled to another module binding another object of the same name needs
    review.
    """
    triage = PullRequestTriager().triage(module_name_kept)
    assert {file.change.path for file in triage.files_needing_review} == {
        PurePosixPath("caller.py"),
        PurePosixPath("shapes/point.py"),
    }

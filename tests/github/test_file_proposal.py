"""
Writing one file of a repository, and proposing it for a default branch.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from basstler.git.branch import Branch
from basstler.github.exceptions import BranchOwnerUnknown
from basstler.github.file_proposal import (
    BranchReferenceRead,
    ExistingBranch,
    FileCommit,
    FileWrite,
    RepositoryFile,
)
from basstler.github.git_objects import EncodedContent
from basstler.github.repository import Repository

from ..constants.paths import DatasetLocation

# %% a committed file

REPOSITORY = Repository("an-owner", "a-project")
"""
The repository every file here is committed to.
"""

COMMIT = FileCommit(
    Branch(REPOSITORY, "trunk"),
    ".github/workflows/a-workflow.yml",
    DatasetLocation.REPOSITORY_TRUNK_DEFAULT_BRANCH.read_text(),
    "Add a workflow",
)
"""
A workflow committed to the repository's default branch.
"""

CURRENT = RepositoryFile(
    object_hash="a-blob", content=EncodedContent.encode("an older version\n")
)
"""
Another version of the file, already on the branch.
"""


def test_a_new_file_is_written_without_a_blob_to_replace():
    assert "sha" not in COMMIT.write_replacing(None).to_json()


def test_a_file_already_there_is_replaced_by_its_blob():
    assert COMMIT.write_replacing(CURRENT).to_json()["sha"] == CURRENT.object_hash


def test_the_written_content_decodes_to_the_committed_text():
    assert COMMIT.write_replacing(None).text == COMMIT.text


def test_a_file_write_changes_a_repository_file():
    assert FileWrite.resource_type is RepositoryFile


# %% a branch, as the git references API names it


def test_an_existing_branch_is_read_as_the_branch_of_the_read_s_repository():
    branch = Branch(REPOSITORY, "a-feature")
    existing = BranchReferenceRead(REPOSITORY, branch).parse(
        {"ref": branch.reference, "object": {"sha": "a-commit"}}
    )
    assert existing.branch == branch


def test_a_branch_read_outside_a_read_has_no_known_repository():
    with pytest.raises(ValidationError) as raised:
        ExistingBranch.from_json(
            {"ref": f"{Branch.namespace}/a-feature", "object": {"sha": "a-commit"}}
        )
    assert isinstance(raised.value.errors()[0]["ctx"]["error"], BranchOwnerUnknown)

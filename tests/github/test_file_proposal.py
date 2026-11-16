"""
Writing one file of a repository, and proposing it for a default branch.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from basstler.git.branch import Branch
from basstler.github.file_proposal import (
    FileCommit,
    FileWrite,
    NewFileForm,
    NewFileParameter,
    RepositoryFile,
)
from basstler.github.git_objects import EncodedContent
from basstler.github.repository import Repository
from basstler.github.repository_resources import SettingWrite
from basstler.github.user_steps import AddFile, ReplaceFile

from ..constants.paths import DatasetLocation

# %% a committed file

REPOSITORY = Repository("an-owner", "a-project")
"""
The repository every file here is committed to.
"""

COMMIT = FileCommit(
    REPOSITORY,
    Branch("trunk"),
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
    assert FileWrite.setting_type is RepositoryFile
    assert issubclass(FileWrite, SettingWrite)


# %% committing it by hand


def test_a_new_file_left_to_the_user_is_added_from_the_filled_in_page():
    step = COMMIT.write_replacing(None).manual_step
    assert step == AddFile(
        f"{COMMIT.file_path_from_repository_root} on {REPOSITORY.full_name}'s "
        f"{COMMIT.branch.name}",
        NewFileForm(
            REPOSITORY,
            COMMIT.branch,
            COMMIT.file_path_from_repository_root,
            COMMIT.text,
        ).url,
    )


def test_a_replaced_file_left_to_the_user_is_pasted_whole_on_its_edit_page():
    step = COMMIT.write_replacing(CURRENT).manual_step
    assert (type(step), step.text) == (ReplaceFile, COMMIT.text)


# %% the page adding the file


def test_the_new_file_page_fills_in_the_file_s_path_and_content():
    form = NewFileForm(
        REPOSITORY, COMMIT.branch, COMMIT.file_path_from_repository_root, COMMIT.text
    )
    query = parse_qs(urlsplit(form.url).query)
    assert (query[NewFileParameter.FILE_NAME], query[NewFileParameter.VALUE]) == (
        [form.file_path_from_repository_root],
        [form.text],
    )

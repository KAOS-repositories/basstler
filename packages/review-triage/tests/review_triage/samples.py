"""
The file versions and pull requests the review triage suites read.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from basstler.class_property import classproperty
from basstler.git.commit_range import FileVersions
from basstler.text_file import TextFile

from basstler_testing.constants.paths import DatasetLocation

# %% one file in two versions


class FileSample(StrEnum):
    """
    A file in a base and a head version, by the directory holding both.
    """

    BEHAVIOUR_CHANGED = "behaviour-changed"
    CODE_REFORMATTED = "code-reformatted"
    DOCSTRING_REFLOWED = "docstring-reflowed"
    DOCSTRING_REWORDED = "docstring-reworded"
    DOCUMENTATION_REFLOWED = "documentation-reflowed"
    DOCUMENTATION_RENAMED = "documentation-renamed"
    IDENTIFIER_RENAMED = "identifier-renamed"
    IMPORT_SOURCE_CHANGED = "import-source-changed"
    IMPORTS_REORDERED = "imports-reordered"
    STRING_LITERAL_RENAMED = "string-literal-renamed"

    @property
    def directory(self) -> Path:
        """
        The directory holding both versions.
        """
        return DatasetLocation.REVIEW_TRIAGE / self

    def change(self) -> FileVersions:
        """
        :return: The change from the base to the head version, at a path with their
            suffix.
        """
        base = next(self.directory.glob("base.*"))
        head = next(self.directory.glob("head.*"))
        return FileVersions(
            PurePosixPath(f"sample{base.suffix}"),
            base_text=base.read_text(encoding="utf-8"),
            head_text=head.read_text(encoding="utf-8"),
        )


# %% pull request descriptions


class DescriptionSample(StrEnum):
    """
    A pull request description, by its file name.
    """

    DECLARING = "description.md"
    WITHOUT_DECLARATION = "description-without-declaration.md"
    REJECTING_RENAME = "description-rejecting-rename.md"

    def read(self) -> str:
        """
        :return: The description.
        """
        return (DatasetLocation.REVIEW_TRIAGE / self).read_text(encoding="utf-8")


# %% the pull request


class SampleTrees(StrEnum):
    """
    The parts of a sample pull request kept in one directory, its two trees among them.
    """

    @classproperty
    def directory_name(cls) -> str:
        """
        The name of the directory holding the parts.
        """
        raise NotImplementedError

    @property
    def path(self) -> Path:
        """
        Where the part is.
        """
        return DatasetLocation.REVIEW_TRIAGE / self.directory_name / self

    def files(self) -> dict[Path, str]:
        """
        :return: The content of each file of this tree, by its path in the tree.
        """
        return {
            file.relative_to(self.path): TextFile(file).read()
            for file in self.path.rglob("*")
            if file.is_file()
        }


class PullRequestSample(SampleTrees):
    """
    The parts of the sample pull request: its two trees, its REST payload and its
    report.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"
    PAYLOAD = "pull-request.json"
    REPORT = "report.md"

    @classproperty
    def directory_name(cls) -> str:
        return "pull-request"

    def payload(self) -> dict[str, Any]:
        """
        :return: The REST payload, parsed.
        """
        return json.loads(TextFile(self.path).read())


# %% an import respelled to another module that still exists


class ModuleNameKeptSample(SampleTrees):
    """
    A pull request respelling an import to another module binding another object of the
    same name, while the module it imported from stays.
    """

    BASE_TREE = "base"
    HEAD_TREE = "head"

    @classproperty
    def directory_name(cls) -> str:
        return "module-name-kept"

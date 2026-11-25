"""
Which files of a repository are its tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

# %% the layout


@dataclass(frozen=True)
class PytestFileLayout:
    """
    The names that mark a file as a test, as pytest's conventions spell them.
    """

    directories: frozenset[str] = frozenset({"test", "tests"})
    """
    The names of the directories every file below which is a test.
    """

    name_prefix: str = "test_"
    """
    The start of the name of a test module.
    """

    stem_suffix: str = "_test"
    """
    The end of the name of a test module, before its extension.
    """

    fixture_module: str = "conftest.py"
    """
    The name of the module holding the fixtures of the tests beside it.
    """

    def holds(self, path: PurePosixPath) -> bool:
        """
        :param path: A file's path in the repository.
        :return: Whether the file is a test or lies in a test directory.
        """
        return (
            path.name == self.fixture_module
            or path.name.startswith(self.name_prefix)
            or path.stem.endswith(self.stem_suffix)
            or not self.directories.isdisjoint(path.parts[:-1])
        )

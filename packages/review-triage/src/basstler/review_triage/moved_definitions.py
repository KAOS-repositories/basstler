"""
The definitions a pull request moves from one module to another, with the base version
of the module each one left.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import DOTTED_NAME_SEPARATOR

# %% one moved definition


@dataclass(frozen=True)
class MovedDefinition:
    """
    A top-level definition that left one module for another.
    """

    source_path: PurePosixPath
    """
    The file of the module it left, in the base commit.
    """

    source_text: str
    """
    The base version of the module it left.
    """

    source_package: tuple[str, ...]
    """
    The package the module it left is in, in the base commit.
    """

    target_path: PurePosixPath
    """
    The file of the module it moved into, in the head commit.
    """

    old_path: str
    """
    Its dotted path in the module it left.
    """

    new_path: str
    """
    Its dotted path in the module it moved into.
    """

    @property
    def old_name(self) -> str:
        """
        The name the module it left defines it by.
        """
        return self.old_path.rpartition(DOTTED_NAME_SEPARATOR)[2]

    @property
    def new_name(self) -> str:
        """
        The name the module it moved into defines it by.
        """
        return self.new_path.rpartition(DOTTED_NAME_SEPARATOR)[2]

    def name_in(self, source_version: PythonSource) -> str:
        """
        :param source_version: A version of the module it left, its occurrences
            possibly renamed already.
        :return: The name that version defines it by.
        """
        if self.old_name in source_version.defined_names:
            return self.old_name
        return self.new_name

    @property
    def source_module(self) -> str:
        """
        The dotted path of the module it left.
        """
        return self.old_path.rpartition(DOTTED_NAME_SEPARATOR)[0]

    @property
    def source(self) -> PythonSource:
        """
        The base version of the module it left.
        """
        return PythonSource.from_text(self.source_text, self.source_package)


# %% every moved definition


@dataclass(frozen=True)
class MovedDefinitions:
    """
    The definitions a pull request moves between modules.
    """

    definitions: tuple[MovedDefinition, ...] = ()
    """
    The moved definitions, ordered by their old dotted path.
    """

    def arriving_at(self, path: PurePosixPath) -> tuple[MovedDefinition, ...]:
        """
        :param path: A file in the head commit.
        :return: The definitions moved into it.
        """
        return tuple(
            definition
            for definition in self.definitions
            if definition.target_path == path
        )

    def leaving(self, path: PurePosixPath) -> tuple[MovedDefinition, ...]:
        """
        :param path: A file in the base commit.
        :return: The definitions moved out of it.
        """
        return tuple(
            definition
            for definition in self.definitions
            if definition.source_path == path
        )

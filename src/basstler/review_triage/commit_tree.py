"""
The Python modules of one commit, searched for their dotted paths and definitions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import PurePosixPath

from basstler.git.commands import GitCommandResult
from basstler.git.commit_tree import CommitTree, GitGrepExitCode
from basstler.review_triage.definitions import DefinitionSearch
from basstler.review_triage.renames import DOTTED_NAME_SEPARATOR

# %% the search

PYTHON_FILE_PATTERNS = ("*.py", "*.pyi")
"""
The path patterns of the Python files a definition is searched in.
"""

DEFINITION_PATTERN = (
    r"^[[:space:]]*(async[[:space:]]+)?(def|class)[[:space:]]+[A-Za-z_][A-Za-z0-9_]*"
)
"""
Matches the start of a line defining a function, method or class, up to its name.
"""

CLASS_HEADER_PATTERN = (
    r"^[[:space:]]*class[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*[(\\]"
)
"""
Matches the start of a line defining a class that has bases or continues on the next
line.
"""

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
"""
Matches a Python name.
"""

FILE_NAME_TERMINATOR = "\0"
"""
What ``git grep --null`` ends the file name of each line it prints with.
"""

PACKAGE_INITIALIZER = "__init__.py"
"""
The file that makes a directory a package, its own module the package's.
"""

MODULE_SUFFIX = ".py"
"""
The suffix of a Python module's file.
"""

# %% class headers


class BaseListToken(StrEnum):
    """
    The characters that delimit the bases on a line defining a class.
    """

    OPENING = "("
    """
    Starts the bases, or a call or group within them.
    """

    CLOSING = ")"
    """
    Ends what an opening parenthesis started.
    """

    COMMENT = "#"
    """
    Starts a comment, after which the line says nothing of the bases.
    """


@dataclass(frozen=True)
class ClassHeader:
    """
    A line of a commit that starts defining a class with bases.
    """

    file: str
    """
    The key of the file holding it.
    """

    line: str
    """
    The line's text.
    """

    @cached_property
    def bases(self) -> str | None:
        """
        The text between the parentheses around the class's bases, ``None`` unless
        they close on this line before any comment.
        """
        start = self.line.find(BaseListToken.OPENING)
        if start < 0:
            return None
        depth = 0
        for position, character in enumerate(self.line[start:], start):
            if character == BaseListToken.COMMENT:
                return None
            if character == BaseListToken.OPENING:
                depth += 1
            elif character == BaseListToken.CLOSING:
                depth -= 1
            if depth == 0:
                return self.line[start + 1 : position]
        return None


# %% the commit


@dataclass(frozen=True)
class CommitModules(DefinitionSearch):
    """
    The Python modules of one commit.
    """

    tree: CommitTree
    """
    The commit's files.
    """

    def module_path(self, path: PurePosixPath) -> str:
        """
        :param path: A module's file.
        :return: The dotted path the module is imported by, through every enclosing
            directory that is a package.
        """
        components = [] if path.name == PACKAGE_INITIALIZER else [path.stem]
        package = path.parent
        while package != PurePosixPath(".") and self.tree.holds(
            package / PACKAGE_INITIALIZER
        ):
            components.insert(0, package.name)
            package = package.parent
        return DOTTED_NAME_SEPARATOR.join(components)

    def package(self, path: PurePosixPath) -> tuple[str, ...]:
        """
        :param path: A module's file.
        :return: The dotted path's components of the package the module's relative
            imports start from, empty when the file is in no package.
        """
        module = self.module_path(path)
        components = tuple(module.split(DOTTED_NAME_SEPARATOR)) if module else ()
        if path.name == PACKAGE_INITIALIZER:
            return components
        return components[:-1]

    @cached_property
    def module_files(self) -> dict[str, tuple[str, ...]]:
        """
        A key for every ``.py`` file of the commit importable by each dotted path; more
        than one when the path is ambiguous.
        """
        files: dict[str, list[str]] = {}
        for path in sorted(self.tree.file_paths):
            if path.suffix == MODULE_SUFFIX:
                files.setdefault(self.module_path(path), []).append(
                    f"{self.tree.commit}:{path}"
                )
        return {module: tuple(keys) for module, keys in files.items()}

    @cached_property
    def definition_files(self) -> dict[str, tuple[str, ...]]:
        """
        The files defining a function, method or class of each name, listed by one
        search of the whole commit.

        :raises GitCommandFailed: If the search itself fails.
        """
        search = self.tree.git.attempt(
            "grep",
            "--only-matching",
            "--extended-regexp",
            "-e",
            DEFINITION_PATTERN,
            self.tree.commit,
            "--",
            *PYTHON_FILE_PATTERNS,
        )
        files: dict[str, dict[str, None]] = {}
        for line in self.listed_lines(search):
            file, definition = line.rsplit(":", 1)
            files.setdefault(definition.split()[-1], {})[file] = None
        return {name: tuple(listed) for name, listed in files.items()}

    def files_defining(self, names: frozenset[str]) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                file for name in names for file in self.definition_files.get(name, ())
            )
        )

    @cached_property
    def class_headers(self) -> tuple[ClassHeader, ...]:
        """
        Every line of the commit starting a class with bases, listed by one search.

        :raises GitCommandFailed: If the search itself fails.
        """
        search = self.tree.git.attempt(
            "grep",
            "--null",
            "--extended-regexp",
            "-e",
            CLASS_HEADER_PATTERN,
            self.tree.commit,
            "--",
            *PYTHON_FILE_PATTERNS,
        )
        return tuple(
            ClassHeader(*line.split(FILE_NAME_TERMINATOR, 1))
            for line in self.listed_lines(search)
        )

    @cached_property
    def files_by_base(self) -> dict[str, tuple[str, ...]]:
        """
        The files naming each word among the bases a class header lists on its line.
        """
        files: dict[str, dict[str, None]] = {}
        for header in self.class_headers:
            for word in IDENTIFIER.findall(header.bases or ""):
                files.setdefault(word, {})[header.file] = None
        return {word: tuple(listed) for word, listed in files.items()}

    @cached_property
    def files_with_unlisted_bases(self) -> tuple[str, ...]:
        """
        The files with a class header whose bases its line does not list in full.
        """
        return tuple(
            dict.fromkeys(
                header.file for header in self.class_headers if header.bases is None
            )
        )

    def files_subclassing(self, name: str) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (*self.files_by_base.get(name, ()), *self.files_with_unlisted_bases)
            )
        )

    def texts_of(self, files: tuple[str, ...]) -> dict[str, str]:
        return self.tree.git.object_texts(files)

    @staticmethod
    def listed_lines(search: GitCommandResult) -> tuple[str, ...]:
        """
        :param search: A finished ``git grep``.
        :return: The lines it printed, none when nothing matched.
        :raises GitCommandFailed: If the search itself failed.
        """
        if search.exit_status == GitGrepExitCode.NO_MATCH:
            return ()
        return tuple(search.raise_if_failed().output.splitlines())

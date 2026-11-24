"""
Telling which top-level definition a pull request adds carries on one it removes, by how
alike their code is.
"""

from __future__ import annotations

import ast
import difflib
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property

from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.commit_tree import MODULE_SUFFIX, CommitModules
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import DOTTED_NAME_SEPARATOR

# %% one definition's code


@dataclass(frozen=True)
class DefinitionCode:
    """
    The code of one top-level definition, formatting and comments left out.
    """

    kind: type[ast.stmt]
    """
    The kind of statement defining it.
    """

    lines: tuple[str, ...]
    """
    Its statement, unparsed, one entry per line.
    """

    @classmethod
    def from_statement(cls, statement: ast.stmt) -> DefinitionCode:
        """
        :param statement: A top-level statement defining one name.
        :return: Its code.
        """
        kind = type(statement)
        if isinstance(statement, ast.AsyncFunctionDef):
            kind = ast.FunctionDef
        return cls(kind, tuple(ast.unparse(statement).splitlines()))

    def likeness(self, other: DefinitionCode) -> float:
        """
        :param other: Another definition's code.
        :return: The share of their lines the two have in common, in order, from 0 to
            1; 0 when they are different kinds of statement.
        """
        if self.kind is not other.kind:
            return 0.0
        return difflib.SequenceMatcher(
            None, self.lines, other.lines, autojunk=False
        ).ratio()


# %% the definitions of one commit


@dataclass(frozen=True)
class CommitDefinitions:
    """
    The top-level definitions of the modules a pull request changes, in one commit, by
    dotted path.
    """

    definitions: dict[str, DefinitionCode]
    """
    The code of each definition only one statement of one module makes.
    """

    @classmethod
    def from_modules(
        cls, sources: Iterator[tuple[str, PythonSource]]
    ) -> CommitDefinitions:
        """
        :param sources: The dotted path of each module with its version in the commit.
        :return: The definitions those versions make.
        """
        found: dict[str, list[ast.stmt]] = {}
        for module, source in sources:
            for statement in source.tree.body:
                for name in PythonSource.names_defined_by(statement):
                    path = f"{module}{DOTTED_NAME_SEPARATOR}{name}"
                    found.setdefault(path, []).append(statement)
        return cls(
            {
                path: DefinitionCode.from_statement(statements[0])
                for path, statements in found.items()
                if len(statements) == 1
            }
        )


# %% which added definition carries on a removed one


@dataclass(frozen=True)
class DefinitionSuccession:
    """
    Pairs each top-level definition a pull request removes with the one it adds that is
    most like it, where each of the two is the other's single closest match.
    """

    base: CommitDefinitions
    """
    The definitions of the changed modules in the base commit.
    """

    head: CommitDefinitions
    """
    The definitions of the changed modules in the head commit.
    """

    @classmethod
    def from_changes(cls, changes: PullRequestChanges) -> DefinitionSuccession:
        """
        :param changes: A pull request and the files it changes.
        :return: The succession of the definitions of its Python modules.
        """
        modules = [
            change
            for change in changes.files
            if change.path.suffix == MODULE_SUFFIX
            and PythonSource.every_version_parses(change)
        ]
        base = CommitModules(changes.commits.base_tree)
        head = CommitModules(changes.commits.head_tree)
        return cls(
            CommitDefinitions.from_modules(
                (
                    base.module_path(change.previous_path or change.path),
                    PythonSource.from_text(change.base_text),
                )
                for change in modules
                if change.base_text is not None
            ),
            CommitDefinitions.from_modules(
                (
                    head.module_path(change.path),
                    PythonSource.from_text(change.head_text),
                )
                for change in modules
                if change.head_text is not None
            ),
        )

    @cached_property
    def successors(self) -> dict[str, str]:
        """
        The dotted path of the added definition carrying on each removed one, by the
        removed one's dotted path.
        """
        removed = sorted(self.base.definitions.keys() - self.head.definitions.keys())
        added = sorted(self.head.definitions.keys() - self.base.definitions.keys())
        likeness = {
            (old, new): self.base.definitions[old].likeness(self.head.definitions[new])
            for old in removed
            for new in added
        }
        closest_added = {
            old: self.single_closest({new: likeness[old, new] for new in added})
            for old in removed
        }
        closest_removed = {
            new: self.single_closest({old: likeness[old, new] for old in removed})
            for new in added
        }
        return {
            old: new
            for old, new in closest_added.items()
            if new is not None and closest_removed[new] == old
        }

    def is_uncontested(self, old: str, new: str) -> bool:
        """
        :param old: The dotted path of a removed definition.
        :param new: The dotted path of an added one.
        :return: Whether neither is paired with another definition.
        """
        predecessors = {added: removed for removed, added in self.successors.items()}
        return (
            self.successors.get(old, new) == new and predecessors.get(new, old) == old
        )

    @staticmethod
    def single_closest(likeness: dict[str, float]) -> str | None:
        """
        :param likeness: How alike each candidate is to one definition.
        :return: The candidate more alike than every other and alike at all, ``None``
            when there is none.
        """
        ranked = sorted(likeness.items(), key=lambda item: item[1], reverse=True)
        if not ranked or ranked[0][1] == 0:
            return None
        if len(ranked) > 1 and ranked[1][1] == ranked[0][1]:
            return None
        return ranked[0][0]

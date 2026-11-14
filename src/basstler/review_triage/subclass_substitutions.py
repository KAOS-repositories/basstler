"""
Finding the classes a pull request may replace by a subclass made only of members moved
down from them, as renames a file may follow.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass

from basstler.class_property import classproperty
from basstler.review_triage.commit_tree import MODULE_SUFFIX
from basstler.review_triage.comparison import FileChange
from basstler.review_triage.pull_request import PullRequestChanges
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import (
    DOTTED_NAME_SEPARATOR,
    Rename,
    RenameDecisions,
    RenameMap,
)

# %% one class and its subclass


@dataclass(frozen=True)
class ClassVersions:
    """
    A class the pull request keeps, as its base and head commits define it.
    """

    module: str
    """
    The dotted path of the module defining it in the base commit.
    """

    base: ast.ClassDef
    """
    The class in the base commit.
    """

    head: ast.ClassDef
    """
    The class in the head commit.
    """

    @classmethod
    def of(cls, change: FileChange, module: str, name: str) -> ClassVersions | None:
        """
        :param change: A module both commits hold.
        :param module: Its dotted path in the base commit.
        :param name: A class's name.
        :return: The class's versions, ``None`` when either commit's module defines
            no top-level class of that name.
        """
        base, head = (
            next(
                (
                    statement
                    for statement in PythonSource(text or "").tree.body
                    if isinstance(statement, ast.ClassDef) and statement.name == name
                ),
                None,
            )
            for text in (change.base_text, change.head_text)
        )
        if base is None or head is None:
            return None
        return cls(module, base, head)

    def is_substituted_by(self, subclass: ast.ClassDef) -> bool:
        """
        :param subclass: A class the head commit adds, deriving from this one alone.
        :return: Whether it is decorated as this class is, and holds nothing but
            members this class held unchanged in the base commit and no longer holds.
        """
        if ast.dump(ast.Module(subclass.decorator_list, [])) != ast.dump(
            ast.Module(self.base.decorator_list, [])
        ):
            return False
        base_members = {ast.dump(member) for member in self.base.body}
        head_names = {
            member.name
            for member in self.head.body
            if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        members = [
            member
            for member in subclass.body
            if not PythonSource.is_documentation(member)
        ]
        return bool(members) and all(
            isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef)
            and member.name not in head_names
            and ast.dump(member) in base_members
            for member in members
        )


@dataclass(frozen=True)
class SubclassCandidate:
    """
    A class the head commit adds deriving from one imported class alone.
    """

    subclass: ast.ClassDef
    """
    The added class.
    """

    class_path: str
    """
    The dotted path its base class is imported by.
    """

    subclass_path: str
    """
    The dotted path the added class is imported by.
    """


# %% detection


@dataclass(frozen=True)
class SubclassSubstitutionDetection:
    """
    Detects a class the head commit keeps and derives a new subclass from, holding only
    members moved down into it: a file may use the subclass in the class's place.
    """

    @classproperty
    def label(cls) -> str:
        """
        What the substitutions it finds are labelled with.
        """
        return "subclass substitution"

    def substitutions(self, changes: PullRequestChanges) -> RenameMap:
        """
        :param changes: A pull request and the files it changes.
        :return: The class each such subclass may replace, as its name and its dotted
            path.
        """
        candidates = [
            candidate
            for change in changes.files
            if change.path.suffix == MODULE_SUFFIX and change.head_text is not None
            for candidate in self.candidates_in(change, changes)
        ]
        if not candidates:
            return RenameMap()
        kept_modules = {
            changes.commits.base_tree.module_path(
                change.previous_path or change.path
            ): (change)
            for change in changes.files
            if change.path.suffix == MODULE_SUFFIX
            and change.base_text is not None
            and change.head_text is not None
        }
        renames = []
        for candidate in candidates:
            module, _, name = candidate.class_path.rpartition(DOTTED_NAME_SEPARATOR)
            change = kept_modules.get(module)
            versions = change and ClassVersions.of(change, module, name)
            if versions is None or not versions.is_substituted_by(candidate.subclass):
                continue
            renames.append(Rename(name, candidate.subclass.name, self.label))
            renames.append(
                Rename(candidate.class_path, candidate.subclass_path, self.label)
            )
        return RenameMap.of([RenameDecisions(tuple(renames))])

    @staticmethod
    def candidates_in(
        change: FileChange, changes: PullRequestChanges
    ) -> Iterator[SubclassCandidate]:
        """
        :param change: A module the head commit holds.
        :param changes: The pull request.
        :return: Each class the module adds deriving from one imported class alone.
        """
        head = PythonSource(change.head_text or "", change.path.parent.parts)
        base_names = (
            PythonSource(change.base_text).defined_names
            if change.base_text is not None
            else frozenset()
        )
        for subclass in head.tree.body:
            if (
                not isinstance(subclass, ast.ClassDef)
                or subclass.name in base_names
                or subclass.keywords
                or len(subclass.bases) != 1
                or not isinstance(subclass.bases[0], ast.Name)
            ):
                continue
            sources = head.import_bindings.sources_of(subclass.bases[0].id)
            if len(sources) != 1:
                continue
            yield SubclassCandidate(
                subclass,
                next(iter(sources)),
                f"{changes.commits.head_tree.module_path(change.path)}"
                f"{DOTTED_NAME_SEPARATOR}{subclass.name}",
            )

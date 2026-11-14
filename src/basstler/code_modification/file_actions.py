"""
Actions that change the files of a source tree, each with its exact inverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import libcst

from basstler.code_modification.actions import Action, AppliedAction
from basstler.code_modification.exceptions import (
    FileActionTargetError,
    FileExpectation,
)
from basstler.code_modification.source_tree import SourceTree

# %% moving, creating and deleting files


@dataclass(frozen=True)
class FileMove(Action[SourceTree]):
    """
    Moves one file to a path no file of the tree holds.
    """

    source: Path
    """
    The file moved, relative to the tree's root.
    """

    destination: Path
    """
    Where it goes, relative to the tree's root.
    """

    def apply(self, target: SourceTree) -> AppliedAction[SourceTree]:
        if self.source not in target.files:
            raise FileActionTargetError(self.source, FileExpectation.PRESENT)
        if self.destination in target.files:
            raise FileActionTargetError(self.destination, FileExpectation.ABSENT)
        return AppliedAction(
            target.with_files(
                {self.destination: target.files[self.source]}, (self.source,)
            ),
            FileMove(self.destination, self.source),
        )


@dataclass(frozen=True)
class FileCreation(Action[SourceTree]):
    """
    Creates one file at a path no file of the tree holds.
    """

    path: Path
    """
    The file created, relative to the tree's root.
    """

    content: bytes
    """
    What the file holds.
    """

    def apply(self, target: SourceTree) -> AppliedAction[SourceTree]:
        if self.path in target.files:
            raise FileActionTargetError(self.path, FileExpectation.ABSENT)
        return AppliedAction(
            target.with_files({self.path: self.content}),
            FileDeletion(self.path, self.content),
        )


@dataclass(frozen=True)
class FileDeletion(Action[SourceTree]):
    """
    Deletes one file holding exactly the content named.
    """

    path: Path
    """
    The file deleted, relative to the tree's root.
    """

    content: bytes
    """
    What the file must hold, and what the inverse creates it with again.
    """

    def apply(self, target: SourceTree) -> AppliedAction[SourceTree]:
        if target.files.get(self.path) != self.content:
            raise FileActionTargetError(self.path, FileExpectation.CONTENT)
        return AppliedAction(
            target.with_files({}, (self.path,)), FileCreation(self.path, self.content)
        )


# %% changing a module of the tree


@dataclass(frozen=True)
class ModuleEdit(Action[SourceTree]):
    """
    Applies an action to one Python module of the tree.
    """

    path: Path
    """
    The module changed, relative to the tree's root; read and written as UTF-8.
    """

    action: Action[libcst.Module]
    """
    The change made to it.
    """

    def apply(self, target: SourceTree) -> AppliedAction[SourceTree]:
        if self.path not in target.files:
            raise FileActionTargetError(self.path, FileExpectation.PRESENT)
        module = libcst.parse_module(target.files[self.path].decode(encoding="utf-8"))
        applied = self.action.apply(module)
        return AppliedAction(
            target.with_files(
                {self.path: applied.result.code.encode(encoding="utf-8")}
            ),
            ModuleEdit(self.path, applied.inverse),
        )

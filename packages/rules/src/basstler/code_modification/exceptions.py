"""
The errors raised while applying an action to a module or a source tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from libcst.metadata import CodeRange

from basstler.exceptions import DataclassException


@dataclass
class ActionTargetMissingError(DataclassException, LookupError):
    """
    Raised when the module an action is applied to has no node where the action expects
    the node it changes.
    """

    location: CodeRange
    """
    Where the action expected the node.
    """

    node_type: str
    """
    The name of the expected node's type.
    """

    def error_message(self) -> str:
        start, end = self.location.start, self.location.end
        return (
            f"no {self.node_type} from {start.line}:{start.column} to "
            f"{end.line}:{end.column} matches the node the action changes"
        )

    def suggest_correction(self) -> str:
        return (
            "Apply the action to the module it was made for, or to the module the "
            "action before it in its plan produced."
        )


class FileExpectation(StrEnum):
    """
    What a file action expects of the file it changes.
    """

    PRESENT = "present"
    """
    The tree holds the file.
    """

    ABSENT = "absent"
    """
    The tree holds no file at the path.
    """

    CONTENT = "holding the content the action names"
    """
    The tree holds the file with exactly the content the action names.
    """


@dataclass
class FileActionTargetError(DataclassException, LookupError):
    """
    Raised when the tree a file action is applied to does not hold its file as the action
    expects.
    """

    path: Path
    """
    The file the action changes, relative to the tree's root.
    """

    expectation: FileExpectation
    """
    What the action expected of the file.
    """

    def error_message(self) -> str:
        return f"{self.path.as_posix()} is not {self.expectation}"

    def suggest_correction(self) -> str:
        return (
            "Apply the action to the tree it was made for, or to the tree the action "
            "before it in its plan produced."
        )


@dataclass
class UnrewritableImportError(DataclassException, ValueError):
    """
    Raised when a relocation would have to rewrite an import whose rewrite changes the
    name the statement binds.
    """

    path: Path
    """
    The module holding the import, relative to the tree's root.
    """

    line: int
    """
    The line the import starts on, counted from one.
    """

    module: str
    """
    The dotted name of the moved module the statement imports.
    """

    def error_message(self) -> str:
        return (
            f"{self.path.as_posix()}:{self.line} imports {self.module} by its dotted "
            "name, which binds a name a moved module no longer has"
        )

    def suggest_correction(self) -> str:
        return (
            f"Import it as 'from <package> import <module>' or 'import {self.module} "
            "as <name>' before relocating it."
        )

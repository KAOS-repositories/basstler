"""
Finds directories removed with :func:`shutil.rmtree` instead of through
:class:`basstler.directory_tree.DirectoryTree`, and fixes the calls it can.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import override

import libcst
from libcst.metadata import CodeRange

from basstler import directory_tree
from basstler.class_property import classproperty
from basstler.code_modification.imports import ImportedName
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification
from basstler.code_rules.checker import CodeRuleViolation
from basstler.code_rules.commands import CodeRulesCommand
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
)
from basstler.directory_tree import DirectoryTree

# %% the places


class RemovalKeyword(StrEnum):
    """
    The keyword of :func:`shutil.rmtree` that :class:`DirectoryTree` has a field for.
    """

    IGNORE_ERRORS = "ignore_errors"
    """
    Whether errors during the removal are ignored.
    """


@dataclass(frozen=True)
class TreeRemovalCall(Specification):
    """
    A call of :func:`shutil.rmtree` that :class:`DirectoryTree` can take over.
    """

    node: libcst.Call
    """
    The call, which has the directory as its one positional argument and at most the
    ``ignore_errors`` keyword.
    """


# %% the fix


class DirectoryTreeFix(CodeFix[TreeRemovalCall]):
    """
    Removes the directory through :class:`DirectoryTree`, which keeps ignoring errors
    where the call ignored them.
    """

    @classproperty
    def behaviour(cls) -> BehaviourDeclaration:
        return BehaviourDeclaration(
            BehaviourEffect.CHANGED,
            "A read-only entry is made writable and removed instead of stopping the "
            "removal; errors the call ignored are still ignored, apart from a "
            "permission error that making the entry writable does not cure.",
        )

    @classproperty
    def imports(cls) -> tuple[ImportedName, ...]:
        return (ImportedName(DirectoryTree.__module__, DirectoryTree.__name__),)

    def replacement(self, specification: TreeRemovalCall) -> libcst.CSTNode:
        call = specification.node
        tree = call.with_changes(func=libcst.Name(DirectoryTree.__name__))
        return libcst.Call(
            func=libcst.Attribute(
                value=tree, attr=libcst.Name(DirectoryTree.remove.__name__)
            )
        )


# %% the check


@dataclass(frozen=True)
class TreeRemovalChecker(FixableChecker[TreeRemovalCall]):
    """
    Finds calls to :func:`shutil.rmtree` outside :mod:`basstler.directory_tree`; they stop
    at the read-only object files git leaves on Windows.
    """

    @classproperty
    def fix(cls) -> CodeFix[TreeRemovalCall]:
        return DirectoryTreeFix()

    @classproperty
    def violation_description(cls) -> str:
        return (
            f"removes a directory with {shutil.__name__}.{shutil.rmtree.__name__}, "
            "which stops at a read-only entry; call "
            f"{DirectoryTree.__name__}(...).{DirectoryTree.remove.__name__}()"
        )

    @override
    def specifications_of_module(
        self, module: PositionedModule
    ) -> Iterator[TreeRemovalCall]:
        for node, location in self.rmtree_calls(module):
            if self.is_replaceable(node):
                yield TreeRemovalCall(location, node)

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        if path.resolve() == Path(directory_tree.__file__).resolve():
            return
        yield from super().violations(path)
        module = PositionedModule(libcst.parse_module(path.read_text(encoding="utf-8")))
        for node, location in self.rmtree_calls(module):
            if self.is_replaceable(node):
                continue
            yield CodeRuleViolation(
                path,
                location.start.line,
                location.end.line,
                f"{self.violation_description}; it passes more than the directory "
                f"and {RemovalKeyword.IGNORE_ERRORS}, so "
                f"`{CodeRulesCommand.FIX.invocation}` leaves it",
            )

    @staticmethod
    def rmtree_calls(
        module: PositionedModule,
    ) -> Iterator[tuple[libcst.Call, CodeRange]]:
        """
        :return: Every call to :func:`shutil.rmtree` in *module*, with its code range.
        """
        for node, location in module.positions.items():
            if (
                isinstance(node, libcst.Call)
                and isinstance(node.func, libcst.Attribute)
                and node.func.attr.value == shutil.rmtree.__name__
                and isinstance(node.func.value, libcst.Name)
                and node.func.value.value == shutil.__name__
            ):
                yield node, location

    @staticmethod
    def is_replaceable(call: libcst.Call) -> bool:
        """
        :return: Whether *call* passes the directory by position and nothing else but
            ``ignore_errors``, which is all :class:`DirectoryTree` can take over.
        """
        if not call.args:
            return False
        first, *others = call.args
        return (
            first.keyword is None
            and not first.star
            and all(
                argument.keyword is not None
                and argument.keyword.value == RemovalKeyword.IGNORE_ERRORS
                for argument in others
            )
            and len(others) <= 1
        )

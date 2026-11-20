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
from libcst import matchers

from basstler import directory_tree
from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_file import PythonSourceFile
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

# %% the patterns


class RemovalKeyword(StrEnum):
    """
    The keyword of :func:`shutil.rmtree` that :class:`DirectoryTree` has a field for.
    """

    IGNORE_ERRORS = "ignore_errors"
    """
    Whether errors during the removal are ignored.
    """


class TreeRemovalCall(CodePattern):
    """
    A call to :func:`shutil.rmtree`.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        return matchers.Call(
            func=matchers.Attribute(
                value=matchers.Name(shutil.__name__),
                attr=matchers.Name(shutil.rmtree.__name__),
            )
        )


class ReplaceableTreeRemovalCall(CodePattern):
    """
    A call to :func:`shutil.rmtree` passing the directory by position and nothing else
    but ``ignore_errors``, which is all :class:`DirectoryTree` can take over.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        return matchers.Call(
            func=TreeRemovalCall.matcher.func,
            args=[
                matchers.Arg(keyword=None, star=""),
                matchers.ZeroOrOne(
                    matchers.Arg(keyword=matchers.Name(RemovalKeyword.IGNORE_ERRORS))
                ),
            ],
        )


# %% the fix


class DirectoryTreeFix(CodeFix[Specification]):
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
    def required_import(cls) -> type:
        """
        :class:`~basstler.directory_tree.DirectoryTree`.
        """
        return DirectoryTree

    def replacement(self, specification: Specification) -> libcst.Call:
        call = libcst.ensure_type(specification.node, libcst.Call)
        tree = call.with_changes(func=libcst.Name(DirectoryTree.__name__))
        return libcst.Call(
            func=libcst.Attribute(
                value=tree, attr=libcst.Name(DirectoryTree.remove.__name__)
            )
        )


# %% the check


@dataclass(frozen=True)
class TreeRemovalChecker(FixableChecker[Specification]):
    """
    Finds calls to :func:`shutil.rmtree` outside :mod:`basstler.directory_tree`; they stop
    at the read-only object files git leaves on Windows.
    """

    @classproperty
    def fix(cls) -> CodeFix[Specification]:
        return DirectoryTreeFix()

    @classproperty
    def violation_description(cls) -> str:
        return (
            f"removes a directory with {shutil.__name__}.{shutil.rmtree.__name__}, "
            "which stops at a read-only entry; call "
            f"{DirectoryTree.__name__}(...).{DirectoryTree.remove.__name__}()"
        )

    @override
    def checks(self, path: Path) -> bool:
        """
        Skips :mod:`basstler.directory_tree`; :meth:`FixableChecker.checks`.
        """
        return path.resolve() != Path(directory_tree.__file__).resolve()

    @override
    def specifications_of_module(
        self, module: PositionedModule
    ) -> Iterator[Specification]:
        for occurrence in ReplaceableTreeRemovalCall.found_in(module):
            yield Specification(occurrence.location, occurrence.node)

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        """
        Also reports the calls passing more than the fix takes over, which no fix
        covers; :meth:`FixableChecker.violations`.
        """
        yield from super().violations(path)
        if not self.checks(path):
            return
        module = PositionedModule(PythonSourceFile(path).parse())
        for occurrence in TreeRemovalCall.found_in(module):
            if ReplaceableTreeRemovalCall.matches(occurrence.node):
                continue
            yield CodeRuleViolation(
                path,
                occurrence.location.start.line,
                occurrence.location.end.line,
                f"{self.violation_description}; it passes more than the directory "
                f"and {RemovalKeyword.IGNORE_ERRORS}, so "
                f"`{CodeRulesCommand.FIX.invocation}` leaves it",
            )

"""
Finds directories removed with :func:`shutil.rmtree` instead of through
:class:`basstler.directory_tree.DirectoryTree`.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import override

from libcst import matchers

from basstler import directory_tree
from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.references import ReferenceTo
from basstler.code_rules.checker import CodeRuleViolation
from basstler.code_rules.syntax_tree_checker import SyntaxTreeChecker
from basstler.directory_tree import DirectoryTree

# %% the pattern


class TreeRemovalCall(CodePattern):
    """
    A call to :func:`shutil.rmtree`, whichever way the file imports it.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        return matchers.Call(
            func=ReferenceTo(f"{shutil.__name__}.{shutil.rmtree.__name__}").matcher
        )


# %% the check


@dataclass(frozen=True)
class TreeRemovalChecker(SyntaxTreeChecker):
    """
    Finds calls to :func:`shutil.rmtree` outside :mod:`basstler.directory_tree`; they
    stop at the read-only object files git leaves on Windows.
    """

    @override
    def violations_of_module(
        self, path: Path, module: PositionedModule
    ) -> Iterator[CodeRuleViolation]:
        if path.resolve() == Path(directory_tree.__file__).resolve():
            return
        for occurrence in TreeRemovalCall.found_in(module):
            yield CodeRuleViolation(
                path,
                occurrence.location.start.line,
                occurrence.location.end.line,
                f"removes a directory with {shutil.__name__}."
                f"{shutil.rmtree.__name__}, which stops at a read-only entry; call "
                f"{DirectoryTree.__name__}(...).{DirectoryTree.remove.__name__}()",
            )

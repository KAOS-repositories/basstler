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

from basstler import directory_tree
from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation
from basstler.code_rules.source_module import SourceModule
from basstler.directory_tree import DirectoryTree

# %% the check


@dataclass(frozen=True)
class TreeRemovalChecker(CodeRuleChecker):
    """
    Finds calls to :func:`shutil.rmtree` outside :mod:`basstler.directory_tree`; they stop
    at the read-only object files git leaves on Windows.
    """

    @override
    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        if path.resolve() == Path(directory_tree.__file__).resolve():
            return
        module = SourceModule(path)
        for call in module.calls():
            if not module.refers_to(
                call.func, f"{shutil.__name__}.{shutil.rmtree.__name__}"
            ):
                continue
            yield CodeRuleViolation(
                path,
                module.first_line(call),
                module.last_line(call),
                f"removes a directory with {shutil.__name__}."
                f"{shutil.rmtree.__name__}, which stops at a read-only entry; call "
                f"{DirectoryTree.__name__}(...).{DirectoryTree.remove.__name__}()",
            )

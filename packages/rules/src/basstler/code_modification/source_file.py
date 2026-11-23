"""
Python source files and the concrete syntax trees parsed from them.
"""

from __future__ import annotations

from dataclasses import dataclass

import libcst

from basstler.python_source_file import PythonSourceFile

# %% the file


@dataclass(frozen=True)
class EditablePythonSourceFile(PythonSourceFile):
    """
    A Python source file read as the syntax tree a code modification edits.
    """

    def parse(self) -> libcst.Module:
        """
        :return: The module's concrete syntax tree, which keeps every comment and all
            whitespace of the source.
        """
        return libcst.parse_module(self.read())

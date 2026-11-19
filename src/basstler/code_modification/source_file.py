"""
Python source files and the concrete syntax trees parsed from them.
"""

from __future__ import annotations

from dataclasses import dataclass

import libcst

from basstler.text_file import TextFile

# %% the file


@dataclass(frozen=True)
class PythonSourceFile(TextFile):
    """
    A file holding a Python module's source.
    """

    def parse(self) -> libcst.Module:
        """
        :return: The module's concrete syntax tree, which keeps every comment and all
            whitespace of the source.
        """
        return libcst.parse_module(self.read())

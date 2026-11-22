"""
A Python source file outside any installed package, run as a module of its own.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType


@dataclass(frozen=True)
class PythonSourceFile:
    """
    A ``.py`` file that is loaded by its path rather than imported by its name.
    """

    path: Path
    """
    Where the file is.
    """

    def load_module(self) -> ModuleType:
        """
        Run the file as a fresh module named after its stem, without registering it in
        :data:`sys.modules`.

        :return: The module the file defined.
        """
        specification = importlib.util.spec_from_file_location(
            self.path.stem, self.path
        )
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module

"""
Files holding a Python module's source.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from basstler.python_module import PythonModule
from basstler.text_file import TextFile

INITIALIZER_STEM = "__init__"
"""
The stem of the file that holds a package's own source.
"""


@dataclass(frozen=True)
class PythonSourceFile(TextFile):
    """
    A file holding a Python module's source.
    """

    def module_below(self, directory: Path, package: PythonModule) -> PythonModule:
        """
        :param directory: The directory of *package*, which holds this file.
        :param package: The package whose directory is *directory*.
        :return: The module this file holds, relative to *package*.
        """
        parts = (
            self.path.resolve().relative_to(directory.resolve()).with_suffix("").parts
        )
        if parts[-1] == INITIALIZER_STEM:
            parts = parts[:-1]
        return PythonModule(parts, package)

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

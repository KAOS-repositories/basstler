"""
A path as the bash running the hook scripts writes it.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from basstler.bash import Bash

from basstler_testing.constants.paths import DatasetLocation

# %% the path bash prints


@dataclass(frozen=True)
class BashPath:
    """
    A path as a hook script prints it: Git Bash on Windows writes the temporary directory
    as ``/tmp``, so a script's output names a path differently from Python.
    """

    path: Path
    """
    The path, as Python names it.
    """

    @property
    def text(self) -> str:
        """
        :return: The path as bash writes it.
        """
        return subprocess.run(
            Bash.locate(os.environ).command(
                DatasetLocation.BASH_PATH_SCRIPT, self.path
            ),
            capture_output=True,
            encoding="utf-8",
            check=True,
        ).stdout.removesuffix("\n")

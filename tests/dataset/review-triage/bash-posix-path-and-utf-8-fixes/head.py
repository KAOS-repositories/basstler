"""
Reads the variables a skill's shell configuration defines, and the link to its rules.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from basstler.bash import Bash
from basstler.locations import ProjectLocation


def variable_names(configuration: Path) -> str:
    """
    :return: The names of the variables *configuration* defines.
    """
    result = subprocess.run(
        Bash.locate(os.environ).command(
            "-c",
            f'source "{configuration}" >/dev/null 2>&1; compgen -v',
        ),
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def plans_link(document: Path) -> str:
    """
    :return: The link from *document* to the plans directory.
    """
    return Path(
        os.path.relpath(
            ProjectLocation.PLANS,
            document.parent,
        )
    ).as_posix()

"""
Reads the variables a skill's shell configuration defines, and the link to its rules.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from basstler.locations import ProjectLocation


def variable_names(configuration: Path) -> str:
    """
    :return: The names of the variables *configuration* defines.
    """
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{configuration}" >/dev/null 2>&1; compgen -v',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def plans_link(document: Path) -> str:
    """
    :return: The link from *document* to the plans directory.
    """
    return os.path.relpath(
        ProjectLocation.PLANS,
        document.parent,
    )

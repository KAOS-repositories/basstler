"""
Runs bash by its name in a function with no environment parameter.
"""

from __future__ import annotations

import subprocess
import os
from basstler.bash import Bash


def exit_status(script: str) -> int:
    """
    :return: The status *script* exits with.
    """
    return subprocess.run(Bash.locate(os.environ).command(script)).returncode

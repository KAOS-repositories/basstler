"""
Runs bash by its name in a function with no environment parameter.
"""

from __future__ import annotations

import subprocess
import os
from basstler.bash import Bash


def variable_names(script: str) -> str:
    """
    :return: The names of the variables *script* defines.
    """
    return subprocess.run(Bash.locate(os.environ).command("-c", script), capture_output=True).stdout

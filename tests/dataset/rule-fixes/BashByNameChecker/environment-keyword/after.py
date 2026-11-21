"""
Runs bash by its name with an environment passed to the call, in a function with no
environment parameter.
"""

from __future__ import annotations

import os
import subprocess
from basstler.bash import Bash


def run(script: str) -> None:
    """
    Run *script* in a copy of the process environment.
    """
    subprocess.run(Bash.locate(os.environ).command(script), env=dict(os.environ))

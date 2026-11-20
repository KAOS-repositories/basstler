"""
Runs bash by its name with an environment passed to the call, in a function with no
environment parameter.
"""

from __future__ import annotations

import os
import subprocess
from basstler.bash import Bash


def run(script: str, overrides: dict[str, str]) -> None:
    """
    Run *script* with *overrides* set.
    """
    subprocess.run(Bash.locate(os.environ).command("-c", script), check=True, env={**os.environ, **overrides})

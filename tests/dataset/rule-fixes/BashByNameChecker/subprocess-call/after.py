"""
Runs bash by its name where the environment it runs in is a parameter.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from basstler.bash import Bash


def run(script: str, environment: Mapping[str, str]) -> None:
    """
    Run *script* in *environment*.
    """
    subprocess.run(
        Bash.locate(environment).command("-c", script), check=True, env=environment
    )

"""
Runs bash by its name where the environment it runs in is a parameter.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping


def run(script: str, environment: Mapping[str, str]) -> None:
    """
    Run *script* in *environment*.
    """
    subprocess.run(["bash", "-c", script], check=True, env=environment)

"""
Runs bash by its name with an environment passed to the call, in a function with no
environment parameter.
"""

from __future__ import annotations

import os
import subprocess


def run(script: str, overrides: dict[str, str]) -> None:
    """
    Run *script* with *overrides* as its environment.
    """
    subprocess.run(["bash", script], env=overrides)

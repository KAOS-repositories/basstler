"""
Runs bash by its name with an environment passed to the call, in a function with no
environment parameter.
"""

from __future__ import annotations

import os
import subprocess


def run(script: str) -> None:
    """
    Run *script* in a copy of the process environment.
    """
    subprocess.run(["bash", script], env=dict(os.environ))

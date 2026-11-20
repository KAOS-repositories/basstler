"""
Runs bash by its name in a function with no environment parameter.
"""

from __future__ import annotations

import subprocess


def variable_names(script: str) -> str:
    """
    :return: The names of the variables *script* defines.
    """
    return subprocess.run(["bash", "-c", script], capture_output=True).stdout

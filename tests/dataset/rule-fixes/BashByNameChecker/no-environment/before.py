"""
Runs bash by its name in a function with no environment parameter.
"""

from __future__ import annotations

import subprocess


def exit_status(script: str) -> int:
    """
    :return: The status *script* exits with.
    """
    return subprocess.run(["bash", script]).returncode

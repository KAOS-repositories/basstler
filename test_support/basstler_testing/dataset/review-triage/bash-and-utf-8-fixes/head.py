"""
Runs a module with bash sourcing the shell configuration first.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from basstler.bash import Bash

CONFIGURATION = Path("plugin/hooks/configuration.sh")
"""
The shell configuration.
"""


def command() -> tuple[str, ...]:
    """
    :return: bash sourcing the configuration, then handing over to this interpreter.
    """
    return tuple(
        Bash.locate(os.environ).command(
            "-c",
            'source "$0" && exec "$@"',
            str(CONFIGURATION),
            sys.executable,
        )
    )


def configuration_text() -> str:
    """
    :return: The configuration's text.
    """
    return CONFIGURATION.read_text(encoding="utf-8")

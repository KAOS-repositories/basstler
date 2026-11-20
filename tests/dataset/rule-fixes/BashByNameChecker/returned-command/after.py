"""
Returns a command line that runs bash by its name, with arguments unpacked.
"""

from __future__ import annotations

from collections.abc import Mapping
from basstler.bash import Bash


def command(arguments: list[str], environment: Mapping[str, str]) -> tuple[str, ...]:
    """
    :return: bash, running *arguments*.
    """
    return tuple(Bash.locate(environment).command(*arguments))

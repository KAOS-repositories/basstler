"""
Returns a command line that runs bash by its name, with arguments unpacked.
"""

from __future__ import annotations

from collections.abc import Mapping


def command(arguments: list[str], environment: Mapping[str, str]) -> tuple[str, ...]:
    """
    :return: bash, running *arguments*.
    """
    return ("bash", *arguments)

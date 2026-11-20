"""
Checks a step's report names the stack configuration it saved.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from basstler.locations import ProjectLocation


def saved_settings(checkout: Path) -> dict[str, object]:
    """
    :return: The stack settings saved in *checkout*.
    """
    return tomllib.loads(
        (checkout / ProjectLocation.PERSONAL_STACK_CONFIGURATION).read_text()
    )


def names_the_saved_configuration(detail: str) -> bool:
    """
    :return: Whether *detail* names the personal stack configuration.
    """
    return str(ProjectLocation.PERSONAL_STACK_CONFIGURATION) in detail

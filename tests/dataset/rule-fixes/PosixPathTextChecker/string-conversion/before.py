"""
Looks for a repository path in a command's output, written with str.
"""

from __future__ import annotations

from basstler.locations import ProjectLocation


def names_the_stack_configuration(output: str) -> bool:
    """
    :return: Whether *output* names the personal stack configuration.
    """
    return str(ProjectLocation.PERSONAL_STACK_CONFIGURATION) in output

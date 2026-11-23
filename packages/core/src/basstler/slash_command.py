"""
How a session invokes a skill.
"""

from __future__ import annotations

from enum import StrEnum


class SlashCommand(StrEnum):
    """
    The symbols a slash command is written with.
    """

    PREFIX = "/"
    """
    Starts a slash command, before the skill's name.
    """

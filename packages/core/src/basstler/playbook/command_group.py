"""
A group of commands a distribution mounts on the ``basstler`` command.
"""

from __future__ import annotations

from dataclasses import dataclass

from cyclopts import App

from basstler.playbook.component import PlaybookComponent


@dataclass(frozen=True)
class CommandGroup(PlaybookComponent):
    """
    A command tree mounted on ``basstler`` under its own name.
    """

    app: App
    """
    The tree; its name is the word that invokes it after ``basstler``.
    """

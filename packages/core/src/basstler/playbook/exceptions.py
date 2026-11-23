"""
The errors a playbook raises when it is built or read wrongly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from basstler.exceptions import DataclassException
from basstler.playbook.component import PlaybookComponent


@dataclass
class ComponentNotInPlaybook(DataclassException, LookupError):
    """
    Raised when a component to leave out of a playbook is not in it.
    """

    component: PlaybookComponent
    """
    The component that was not found.
    """

    def error_message(self) -> str:
        return f"the playbook holds no {self.component!r}, so it cannot be left out"

    def suggest_correction(self) -> str:
        return (
            "Leave out only components the playbook holds; list them with "
            "Playbook.components."
        )


@dataclass
class PlaybookNotDeclared(DataclassException, LookupError):
    """
    Raised when a project's playbook module does not declare its playbook.
    """

    path: Path
    """
    The module that was read.
    """

    variable: str
    """
    The module-level name the playbook is read from.
    """

    def error_message(self) -> str:
        return f"{self.path} declares no Playbook named {self.variable}"

    def suggest_correction(self) -> str:
        return (
            f"Assign the project's playbook to {self.variable} in {self.path}, for "
            f"example {self.variable} = DefaultPlaybook(), or delete the file to use "
            "the default playbook."
        )

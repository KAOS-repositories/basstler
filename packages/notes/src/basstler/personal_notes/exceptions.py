"""
The failures of reading and writing the personal-notes branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from basstler.exceptions import DataclassException
from basstler.locations import PluginLocation

# %% the personal-notes branch


@dataclass
class NotesBranchMissingError(DataclassException, RuntimeError):
    """
    Raised when no remote tried holds the personal-notes branch.
    """

    branch: str
    """
    The personal-notes branch that was looked for.
    """

    attempted_remotes: tuple[str, ...]
    """
    Every remote it was fetched from, in order.
    """

    def error_message(self) -> str:
        return (
            f"branch '{self.branch}' doesn't exist yet (tried: "
            f"{', '.join(self.attempted_remotes)})"
        )

    def suggest_correction(self) -> str:
        return f"run {PluginLocation.PERSONAL_NOTES_BRANCH_CREATION_SCRIPT.path_under_exported_root} first"


@dataclass
class NotesPushRejectedError(DataclassException, RuntimeError):
    """
    Raised when the remote rejected every push of a write to the personal-notes branch.
    """

    branch: str
    """
    The personal-notes branch pushed to.
    """

    attempts: int
    """
    How many pushes were made.
    """

    def error_message(self) -> str:
        return f"every one of {self.attempts} pushes to '{self.branch}' was rejected"

    def suggest_correction(self) -> str:
        return "check that this credential may push to the branch, then run it again"


@dataclass
class UnsafeNotesPathError(DataclassException, ValueError):
    """
    Raised when a path to write on the personal-notes branch could leave it.
    """

    path: PurePosixPath
    """
    The refused path.
    """

    def error_message(self) -> str:
        return f"{self.path} would be written outside the personal-notes branch's root"

    def suggest_correction(self) -> str:
        return "give a path relative to the branch's root, with no '..' component"

"""
The failures of the review triage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from basstler.exceptions import DataclassException

# %% splitting the moves out


@dataclass
class UnprovenMoveError(DataclassException, RuntimeError):
    """
    Raised when the commit moving a pull request's definitions changes a file the triage
    cannot prove mechanical, so the split would hide a change in it.
    """

    pull_request: int
    """
    The pull request's number.
    """

    files: tuple[PurePosixPath, ...]
    """
    The files the move commit changes that the triage leaves for review.
    """

    def error_message(self) -> str:
        listed = ", ".join(str(path) for path in self.files)
        return (
            f"the commit moving the definitions of #{self.pull_request} is not proven "
            f"to only move them; the triage leaves {listed} for review"
        )

    def suggest_correction(self) -> str:
        return (
            "review the pull request as it is; nothing was pushed, and its branch is "
            "unchanged"
        )


@dataclass
class MissingHeadRepositoryError(DataclassException, LookupError):
    """
    Raised when the repository a pull request's branch lives in no longer exists, so its
    branch cannot be replaced.
    """

    pull_request: int
    """
    The pull request's number.
    """

    def error_message(self) -> str:
        return f"the repository holding the branch of #{self.pull_request} is deleted"

    def suggest_correction(self) -> str:
        return "review the pull request as it is; its commits cannot be replaced"

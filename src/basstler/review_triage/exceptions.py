"""
The failures of the review triage.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.exceptions import DataclassException

# %% marking files viewed


@dataclass
class PullRequestHeadMoved(DataclassException):
    """
    Raised when a pull request's head commit is no longer the one its files were triaged
    at, so no file is marked viewed.
    """

    number: int
    """
    The pull request's number.
    """

    triaged_commit: str
    """
    The head commit the files were triaged at.
    """

    head_commit: str
    """
    The pull request's head commit now.
    """

    def error_message(self) -> str:
        return (
            f"Pull request {self.number} moved from {self.triaged_commit} to "
            f"{self.head_commit} since its files were triaged; nothing was marked viewed."
        )

    def suggest_correction(self) -> str:
        return "Run mark-viewed again to triage the new head commit."

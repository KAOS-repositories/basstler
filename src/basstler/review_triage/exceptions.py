"""
The failures of the review triage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from basstler.exceptions import DataclassException

# %% splitting the mechanical changes out


@dataclass
class UnprovenSplitError(DataclassException, RuntimeError):
    """
    Raised when the commit making a pull request's mechanical changes changes a file the
    triage cannot prove mechanical, so the split would hide a change in it.
    """

    pull_request: int
    """
    The pull request's number.
    """

    files: tuple[PurePosixPath, ...]
    """
    The files the mechanical commit changes that the triage leaves for review.
    """

    def error_message(self) -> str:
        listed = ", ".join(str(path) for path in self.files)
        return (
            f"the commit making the mechanical changes of #{self.pull_request} is not "
            f"proven mechanical; the triage leaves {listed} for review"
        )

    def suggest_correction(self) -> str:
        return (
            "review the pull request as it is; nothing was pushed, and its branch is "
            "unchanged"
        )


@dataclass
class BaseBranchMergedError(DataclassException, RuntimeError):
    """
    Raised when the base branch was merged into a pull request after the commit its
    split starts from, so the split commits would lose that merge.
    """

    pull_request: int
    """
    The pull request's number.
    """

    start: str
    """
    The commit the split starts from.
    """

    def error_message(self) -> str:
        return (
            f"the base branch was merged into #{self.pull_request} after {self.start}, "
            f"the commit the split starts from"
        )

    def suggest_correction(self) -> str:
        return (
            "split the whole change with --from-merge-base; nothing was pushed, and the "
            "branch is unchanged"
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

"""
The errors triaging a pull request can end in.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from basstler.class_property import classproperty
from basstler.exceptions import DataclassException
from basstler.locations import BasstlerRepositoryLocation
from basstler.github.basstler_project import BasstlerProject
from basstler.github.repository import PullRequestReference, Repository
from basstler.review_triage.command_names import ReviewTriageCommand

# %% the routes a correction offers


class MarkingRoutes:
    """
    The two ways of marking files viewed, as a correction offers them.
    """

    @classproperty
    def readme_url(cls) -> str:
        """
        Where both routes are described, readable from any terminal.
        """
        return BasstlerProject.repository.file_url(
            BasstlerProject.default_branch,
            BasstlerRepositoryLocation.REVIEW_TRIAGE_README.as_posix(),
        )

    @classproperty
    def instructions(cls) -> str:
        """
        How to take either route.
        """
        return (
            "Either mark them from a terminal, or a Claude Code session, on your own "
            "computer, where GitHub's GraphQL API is reachable: log gh in as the "
            "account the files are marked viewed for (gh auth login; gh auth refresh "
            "-s repo when its credential may not write pull requests), then run "
            f"{ReviewTriageCommand.MARK_VIEWED.invocation} <number>. Or have a "
            "repository's Actions mark them, from anywhere: run "
            f"{ReviewTriageCommand.SET_UP_MARK_VIEWED.invocation} and take the steps "
            f"it lists. Both are described at {cls.readme_url}"
        )


# %% errors


@dataclass
class MarkViewedWorkflowRefused(DataclassException):
    """
    Raised when GitHub refuses to start the workflow marking files viewed.
    """

    workflow_repository: Repository
    """
    The repository whose workflow was to be started.
    """

    reason: str
    """
    What GitHub answered.
    """

    def error_message(self) -> str:
        return (
            f"Could not start the mark-viewed workflow of "
            f"{self.workflow_repository.full_name}: {self.reason}"
        )

    def suggest_correction(self) -> str:
        return MarkingRoutes.instructions


@dataclass
class FilesNotMarkedViewed(DataclassException):
    """
    Raised when neither marking files viewed directly nor through a repository's Actions
    succeeded.
    """

    pull_request: PullRequestReference
    """
    The pull request whose files were to be marked.
    """

    direct_refusal: str
    """
    Why marking them directly failed or was not tried.
    """

    workflow_repository: Repository
    """
    The repository whose Actions were asked next.
    """

    workflow_refusal: str
    """
    Why starting its workflow failed.
    """

    def error_message(self) -> str:
        return (
            f"No file of {self.pull_request.url} was marked viewed. Directly: "
            f"{self.direct_refusal}. Through {self.workflow_repository.full_name}'s "
            f"Actions: {self.workflow_refusal}."
        )

    def suggest_correction(self) -> str:
        return MarkingRoutes.instructions


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


@dataclass
class UnknownRecordedPlanError(DataclassException):
    """
    Raised when a commit trailer or an argument names a code modification plan the
    triage does not know.
    """

    plan_name: str
    """
    The name given.
    """

    known_names: tuple[str, ...]
    """
    The names of the plans the triage can replay.
    """

    def error_message(self) -> str:
        return (
            f"No code modification plan the triage replays is named {self.plan_name!r}."
        )

    def suggest_correction(self) -> str:
        return f"Name one of: {', '.join(self.known_names)}."


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

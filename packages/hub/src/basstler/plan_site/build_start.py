"""
Start the plan site's build with this session's own GitHub credential, after a push to
the notes branch, and print whether it started; or check, before any push, that it can.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.plan_site.build_start
    "${BASSTLER_PYTHON}" -m basstler.plan_site.build_start check-access
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from cyclopts import App

from basstler.markdown_code_block import CodeBlockLanguage
from basstler.git.remote import Remote
from basstler.exit_codes import StackExitCode
from basstler.git.commands import GitCommandRunner
from basstler.git.remote_branch import RemoteBranch
from basstler.github.client import (
    GitHubAttemptClient,
    GitHubResponse,
    GitHubRestClient,
)
from basstler.github.credential import GitHubCommand
from basstler.github.repository_attachment import RepositoryAttachment
from basstler.github.repository_details import RepositoryDetailsRead
from basstler.github.workflow_run import WorkflowDispatch
from basstler.locations import BasstlerVariable, ClaudeCodeVariable, WorkflowLocation
from basstler.maintenance.landed_closing import ClosedAsLanded
from basstler.maintenance.landed_closing_follow_up import LandedClosingFollowUp
from basstler.personal_notes.branch import PersonalNotesLocation
from basstler.plan_site.site_repository import SiteRepository
from basstler.plan_site.workflows import PlanSiteSecret
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

# %% the outcome

BUILD_START_COMMAND = f'"${{{BasstlerVariable.PYTHON}}}" -m {__spec__.name}'
"""
The command line that starts the build again, once this session can.
"""


@dataclass(frozen=True)
class SiteAccess:
    """
    Whether this session's credential reaches :attr:`site`, and how to make it reach it.
    """

    site: SiteRepository
    """
    The repository whose build a plan save starts.
    """

    retry_command: str = BUILD_START_COMMAND
    """
    The command that does what failed, once this session reaches :attr:`site`.
    """

    attachment_benefit: str = (
        "every plan save then updates the plan site within a minute, without a stored "
        "token"
    )
    """
    What attaching :attr:`site` gives the user, said when asking them to allow it.
    """

    def read(self, client: GitHubAttemptClient) -> GitHubResponse:
        """
        :param client: Reads the site repository.
        :return: GitHub's answer, which never raises for a refusal.
        """
        return client.attempt_get(self.site.repository.api_path)

    def missing_access(
        self, client: GitHubAttemptClient, in_cloud_session: bool
    ) -> str | None:
        """
        :param client: Reads the site repository.
        :param in_cloud_session: Whether this runs in a Claude Code cloud session.
        :return: Why a plan save could not start the build now and how this session
            gets the access, ``None`` when it has it.
        """
        read = self.read(client)
        if read.failure is None:
            return None
        return (
            f"A plan save cannot start the build in {self.site.repository.full_name} "
            f"yet ({read.failure.error_message()}). {self.remedy(in_cloud_session)}"
        )

    def remedy(self, in_cloud_session: bool) -> str:
        """
        :param in_cloud_session: Whether this runs in a Claude Code cloud session.
        :return: How this session gets the access, and :attr:`retry_command` to run
            then.
        """
        repository = self.site.repository
        if not in_cloud_session:
            return "\n".join(
                [
                    f"Log gh in with an account that can run workflows in "
                    f"{repository.full_name}, then run {self.retry_command}:",
                    "",
                    CodeBlockLanguage.BASH.fenced(GitHubCommand.LOG_IN),
                ]
            )
        return RepositoryAttachment(
            repository,
            retry_command=self.retry_command,
            benefit=self.attachment_benefit,
        ).instruction()


@dataclass(frozen=True)
class BuildStart:
    """
    The attempt to start :attr:`site`'s build workflow.
    """

    site: SiteRepository
    """
    The repository whose build is started.
    """

    response: GitHubResponse
    """
    GitHub's answer: to reading the site repository if that was refused, else to the
    dispatch.
    """

    @classmethod
    def attempt(cls, site: SiteRepository, client: GitHubAttemptClient) -> BuildStart:
        """
        :param site: The site repository.
        :param client: Reads the site repository's default branch and sends the dispatch.
        :return: The attempt, which never raises for a refusal or a call with no answer.
        """
        read = SiteAccess(site).read(client)
        if read.failure is not None:
            return cls(site, read)
        dispatch = client.attempt_send(
            WorkflowDispatch(
                site.repository,
                WorkflowLocation.PLAN_SITE,
                RepositoryDetailsRead(site.repository)
                .parse(read.body)
                .default_branch.name,
            )
        )
        return cls(site, dispatch)

    @property
    def started(self) -> bool:
        """:return: Whether GitHub accepted the dispatch."""
        return self.response.failure is None

    def describe(self, in_cloud_session: bool) -> str:
        """
        :param in_cloud_session: Whether this runs in a Claude Code cloud session.
        :return: What happened, and when the build did not start, how this session
            gets it to start.
        """
        repository = self.site.repository
        if self.started:
            return f"Started the plan site build in {repository.full_name}."
        return (
            f"Could not start the plan site build in {repository.full_name}: "
            f"{self.response.failure.error_message()}. The notes branch's dispatch "
            f"workflow still starts it if {PlanSiteSecret.TOKEN} is stored. "
            f"{SiteAccess(self.site).remedy(in_cloud_session)}"
        )


# %% after a maintenance pass


@dataclass(frozen=True)
class PlanSiteRebuild(LandedClosingFollowUp):
    """
    Starts the plan site's build once a maintenance pass has closed pull requests, so the
    site shows their items done.
    """

    def respond_to_closing(self, closed: Sequence[ClosedAsLanded]) -> str | None:
        return start_recorded_build()


# %% the command line

app = App(help=__doc__)
"""
The command, which takes no arguments.
"""


def recorded_site() -> SiteRepository | None:
    """
    :return: The site repository this clone's notes branch records, ``None`` when no
        plan site lists this repository.
    """
    project_root = Path(
        os.environ.get(ClaudeCodeVariable.PROJECT_DIRECTORY, Path.cwd())
    )
    location = PersonalNotesLocation.resolve(project_root, os.environ)
    return SiteRepository.recorded_on(
        RemoteBranch(
            Remote(GitCommandRunner(project_root), location.remote), location.branch
        )
    )


def start_recorded_build() -> str | None:
    """
    Start the build of the plan site this clone's notes branch records.

    :return: What happened, ``None`` when no plan site lists this repository.
    """
    site = recorded_site()
    if site is None:
        return None
    attempt = BuildStart.attempt(site, GitHubRestClient())
    return attempt.describe(ClaudeCodeVariable.REMOTE.is_true())


@app.default
def start_build() -> StackExitCode:
    """
    Start this clone's plan site build and print what happened.

    :return: :attr:`StackExitCode.SUCCESS`, also when the build did not start: the notes were saved either way.
    """
    outcome = start_recorded_build()
    if outcome is None:
        logger.info("No plan site lists this repository, so no build was started.")
        return StackExitCode.SUCCESS
    logger.info(outcome)
    return StackExitCode.SUCCESS


@app.command(name="check-access")
def check_access() -> StackExitCode:
    """
    Print how this session gets access to the site repository, and nothing when it
    already has it or no plan site lists this repository.

    :return: :attr:`StackExitCode.SUCCESS`, also when the access is missing: the line printed is the answer.
    """
    site = recorded_site()
    if site is None:
        return StackExitCode.SUCCESS
    missing = SiteAccess(site).missing_access(
        GitHubRestClient(), ClaudeCodeVariable.REMOTE.is_true()
    )
    if missing is not None:
        logger.info(missing)
    return StackExitCode.SUCCESS


if __name__ == "__main__":
    app()

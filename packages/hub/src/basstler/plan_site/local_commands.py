"""
The ``basstler plan-site`` commands: serving the plan site on this computer.
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from basstler.git.commands import GitCommandRunner
from basstler.git.remote_branch import RemoteBranch
from basstler.github.login_lending import GitHubLoginLendingRunner
from basstler.github.remote import GitHubRemote
from basstler.github.repository import Repository
from basstler.github.repository_option import RepositoryArgument, RepositoryOption
from basstler.plan_site import local_build
from basstler.plan_site.hub import PlanHub
from basstler.plan_site.local_server import LocalSiteServer, local_site_url
from basstler.plan_site.local_site import LocalSite
from basstler.plan_site.locations import SiteProjectLocation
from basstler.plan_site.user_service import SystemdUserService
from basstler.shell_configuration import PersonalNotesSetting
from basstler.standard_streams import StandardStreamHandler

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its commands print through.
"""


class ServeOption(StrEnum):
    """
    The options the installed service passes back to ``serve``.
    """

    PORT = "--port"
    STALE_AFTER_MINUTES = "--stale-after-minutes"
    REGISTRY = "--registry"
    REPOSITORY = "--repository"


@Parameter(name="*")
@dataclass(frozen=True)
class ServeSettings:
    """
    How the plan site is served on this computer.
    """

    port: int = 8765
    """
    The port on 127.0.0.1 the site is served from.
    """

    stale_after_minutes: float = 5
    """
    How old a build may be before viewing a page builds again.
    """

    registry: RepositoryOption = None
    """
    The repository whose notes hold the hub file, by default the one this checkout's
    notes name.
    """

    repository: tuple[RepositoryArgument, ...] = ()
    """
    The only repositories to show; by default every one you can read that has plans,
    and the hub's.
    """

    @staticmethod
    def registry_of_checkout(project_root: Path) -> Repository | None:
        """
        :param project_root: The directory the command runs in.
        :return: The registry the checkout's notes name, ``None`` when it is no
            checkout or its notes hold no hub file.
        """
        git = GitCommandRunner(project_root)
        if not git.attempt("rev-parse", "--git-dir").succeeded:
            return None
        notes_remote = PersonalNotesSetting.REMOTE.resolve(project_root, os.environ)
        if git.configured_remote_url(notes_remote) is None:
            return None
        notes_branch = RemoteBranch(
            GitHubRemote(GitHubLoginLendingRunner(project_root), notes_remote),
            PersonalNotesSetting.BRANCH.resolve(project_root, os.environ),
        )
        hub = PlanHub.from_yaml(notes_branch.read_latest(SiteProjectLocation.PLAN_HUB))
        if hub is None or hub.registry is None:
            return None
        return Repository.parse(hub.registry)

    def selection_options(self) -> tuple[str, ...]:
        """
        :return: The options choosing the repositories, as the build takes them.
        """
        registry = (
            ()
            if self.registry is None
            else (ServeOption.REGISTRY, str(self.registry))
        )
        narrowed = tuple(
            word
            for repository in self.repository
            for word in (ServeOption.REPOSITORY, str(repository))
        )
        return (*registry, *narrowed)

    def service_command(self) -> tuple[str, ...]:
        """
        :return: The command that serves with these settings from any directory.
        """
        return (
            sys.executable,
            "-m",
            __name__,
            "serve",
            ServeOption.PORT,
            str(self.port),
            ServeOption.STALE_AFTER_MINUTES,
            f"{self.stale_after_minutes:g}",
            *self.selection_options(),
        )

    def with_checkout_registry(self) -> ServeSettings:
        """
        :return: These settings, naming the current checkout's registry when none was
            given.
        """
        if self.registry is not None:
            return self
        return replace(self, registry=self.registry_of_checkout(Path.cwd()))


plan_site_app = App(
    name="plan-site",
    help="Serve the plan site on this computer, private repositories included.",
)
"""
The ``plan-site`` command group.
"""


@plan_site_app.command
def serve(*, settings: Annotated[ServeSettings, Parameter()] = ServeSettings()) -> None:
    """
    Serve the plan site on 127.0.0.1 until stopped.

    A page view rebuilds a stale site; the page's Refresh button rebuilds at once.
    """
    settings = settings.with_checkout_registry()
    build = local_build.SubprocessSiteBuild(
        (
            sys.executable,
            "-m",
            local_build.__name__,
            "--site-url",
            local_site_url(settings.port),
            *settings.selection_options(),
        )
    )
    with tempfile.TemporaryDirectory() as scratch:
        site = LocalSite(
            build,
            Path(scratch),
            stale_after=timedelta(minutes=settings.stale_after_minutes),
        )
        with LocalSiteServer(site, settings.port) as server:
            logger.info(f"The plan site is served at {server.url}")
            server.serve_forever()


@plan_site_app.command
def install_service(
    *, settings: Annotated[ServeSettings, Parameter()] = ServeSettings()
) -> None:
    """
    Keep ``serve`` running as a systemd user service, from now and at every login.
    """
    settings = settings.with_checkout_registry()
    service = SystemdUserService.for_current_user(settings.service_command())
    service.install()
    logger.info(
        f"Installed {service.unit_path}; the plan site is served at "
        f"{local_site_url(settings.port)}"
    )


if __name__ == "__main__":
    plan_site_app()

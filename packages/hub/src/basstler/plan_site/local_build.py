"""
Build the locally served plan site once, private repositories in full.

Usage:
    "${BASSTLER_PYTHON}" -m basstler.plan_site.local_build --output <directory> \\
        --site-url <url> [--registry <owner/name>] [--repository <owner/name> ...]
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cyclopts import App

from basstler.git.commands import TransientGitSetting
from basstler.github.client import GitHubRestClient, GitHubWriter
from basstler.github.login_lending import GitHubLoginLendingRunner
from basstler.github.pull_request_source import (
    GitHubPullRequestSource,
    PullRequestSource,
)
from basstler.github.repository import GitHubAddress
from basstler.github.repository_option import RepositoryArgument, RepositoryOption
from basstler.plan_site.__main__ import HubSite
from basstler.plan_site.hub import SiteAddress
from basstler.plan_site.local_repositories import RepositorySelection
from basstler.plan_site.local_site import SiteBuild

# %% building


def build_local_site(
    selection: RepositorySelection,
    address: SiteAddress,
    pull_request_source: PullRequestSource,
    output: Path,
    github: GitHubWriter | None = None,
) -> None:
    """
    :param selection: Which repositories to publish.
    :param address: The address the site is served from.
    :param pull_request_source: Where the live pull request state comes from.
    :param output: The directory to write the site into.
    :param github: What lists the viewer's repositories.
    """
    hub = selection.hub(github or GitHubRestClient(), address.site_url)
    HubSite(
        address=address,
        pull_request_source=pull_request_source,
        hub=hub,
        remote_root=selection.remote_root,
    ).build(output)


@dataclass(frozen=True)
class SubprocessSiteBuild(SiteBuild):
    """
    Builds the site in a process of its own, with ``gh``'s login lent to its git, so a
    build that fails leaves the server running and says why.
    """

    command: tuple[str, ...]
    """
    The command that builds, given the directory to write into as its last words.
    """

    reported_lines: int = 20
    """
    How many lines from the end of a failed build's error output are reported.
    """

    def build(self, output: Path) -> str | None:
        lent = TransientGitSetting(
            f"credential.{GitHubAddress.WEB}.helper",
            GitHubLoginLendingRunner.credential_helper,
        ).variables(os.environ)
        completed = subprocess.run(
            [*self.command, "--output", str(output)],
            capture_output=True,
            encoding="utf-8",
            env={**os.environ, **lent},
        )
        if completed.returncode == 0:
            return None
        return "\n".join(completed.stderr.splitlines()[-self.reported_lines :])


# %% the command

app = App(help=__doc__)
"""
The command.
"""


@app.default
def build(
    *,
    output: Path,
    site_url: str,
    registry: RepositoryOption = None,
    repository: tuple[RepositoryArgument, ...] = (),
) -> None:
    """
    Build the site as the viewer ``gh`` is logged in as.

    :param output: The directory to write the site into.
    :param site_url: The address the site is served from.
    :param registry: The repository whose notes hold the hub file.
    :param repository: The only repositories to publish, every one when none is named.
    """
    build_local_site(
        RepositorySelection(registry=registry, narrowed_to=repository),
        SiteAddress(site_url),
        GitHubPullRequestSource.from_environment(reads_mergeable_states=True),
        output,
    )


if __name__ == "__main__":
    app()

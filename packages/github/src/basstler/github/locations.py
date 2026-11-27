"""
The files and directories the GitHub client and the models of GitHub's data name.
"""

from __future__ import annotations

from pathlib import Path

from basstler.locations import (
    INSTALLED_PACKAGE,
    BasstlerRepositoryFile,
    BasstlerRepositoryLocation,
    PackageFile,
    PathEnumeration,
    ProjectFile,
    ShippedPath,
)


class GitHubTemplate(PathEnumeration):
    """
    The templates the GitHub client's models render.
    """

    SHARED_TOKEN_STORE_COMMAND = INSTALLED_PACKAGE.shipped(
        ShippedPath.TEMPLATES / "shared_token_store_command.sh"
    )
    """
    The command storing one token, read once at a hidden prompt, as several secrets.
    """


class GitHubPackageLocation(PackageFile):
    """
    The files the github distribution ships.
    """

    QUERIES = INSTALLED_PACKAGE.shipped(Path("github") / "queries")
    """
    The GraphQL documents the upstream review reader sends.
    """


class GitHubProjectLocation(ProjectFile):
    """
    The files the GitHub client reads in a project.
    """

    ACTIONS_BUDGET = Path(".github") / "actions_budget.py"
    """
    The repository's Actions budget: the limits basstler holds every workflow to.
    """


class ReleaseRepositoryLocation(BasstlerRepositoryFile):
    """
    The files of basstler's own repository a release reads.
    """

    PLUGIN_MANIFEST = (
        BasstlerRepositoryLocation.PLUGIN / ".claude-plugin" / "plugin.json"
    )
    """
    The plugin's manifest: its name, description and, once released, version.
    """

    @property
    def path_in_plugin(self) -> Path:
        """
        :return: This file's path from the plugin's root, as the released plugin holds it.
        """
        return self.relative_to(BasstlerRepositoryLocation.PLUGIN)

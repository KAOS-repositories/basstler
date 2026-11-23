"""
The files and directories the GitHub client and the models of GitHub's data name.
"""

from __future__ import annotations

from pathlib import Path

from basstler.locations import INSTALLED_PACKAGE, PathEnumeration, ShippedPath


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


class GitHubPackageLocation(PathEnumeration):
    """
    The files the github distribution ships, as absolute paths.
    """

    QUERIES = INSTALLED_PACKAGE.shipped(Path("github") / "queries")
    """
    The GraphQL documents the upstream review reader sends.
    """


class GitHubProjectLocation(PathEnumeration):
    """
    The files the GitHub client reads in a project, relative to its root.
    """

    WORKFLOWS = Path(".github") / "workflows"
    """
    Where GitHub reads a repository's workflows from - the top level only.
    """

    ACTIONS_BUDGET = Path(".github") / "actions_budget.py"
    """
    The repository's Actions budget: the limits basstler holds every workflow to.
    """


class BasstlerRepositoryLocation(PathEnumeration):
    """
    The directories of basstler's own repository a release reads, relative to its root.
    """

    PLUGIN = Path("plugin")
    """
    The Claude Code plugin.
    """

    PLUGIN_MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
    """
    The plugin's manifest: its name, description and, once released, version.
    """

    @property
    def path_in_plugin(self) -> Path:
        """
        :return: This file's path from the plugin's root, as the released plugin holds it.
        """
        return self.relative_to(BasstlerRepositoryLocation.PLUGIN)

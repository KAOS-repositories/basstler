"""
The files and directories the personal-notes setup names.

.. note:: Imports nothing outside the standard library, since :mod:`basstler.setup.dependencies`
    reads its declaration's location from here before anything is installed.
"""

from __future__ import annotations

from pathlib import Path

from basstler.locations import (
    PackageLocation,
    PathEnumeration,
    PluginFile,
    PluginLocation,
    WorkspaceLocation,
)


class SetupPackageLocation(PathEnumeration):
    """
    The files of a checkout the setup reads, as absolute paths.
    """

    META_PACKAGE_METADATA = (
        PackageLocation.SOURCE_TREE
        / WorkspaceLocation.PACKAGES
        / PackageLocation.DIRECTORY.name
        / WorkspaceLocation.METADATA
    )
    """
    The ``basstler`` distribution's metadata in a checkout: its name, the interpreters
    it supports and where its version is read from.
    """


class SetupPluginLocation(PluginFile):
    """
    The plugin's scripts the setup runs or names, relative to the plugin's root.
    """

    SESSION_START_SCRIPT = PluginLocation.HOOKS / "session-start.sh"
    """
    The session-start hook: sets up the package's environment and loads the personal
    notes.
    """

    SETUP_CHECK_SCRIPT = PluginLocation.HOOKS / "check-setup.sh"
    """
    Reports, one row per prerequisite, what the personal-notes setup still lacks.
    """

    GIT_IDENTITY_SAVING_SCRIPT = PluginLocation.HOOKS / "save-git-identity.sh"
    """
    Saves the user's git identity to the personal-notes branch.
    """


class PluginSkillLocation(PluginFile):
    """
    The files of the plugin's skills this package reads, relative to the plugin's root.
    """

    SKILLS = Path("skills")
    """
    The directory holding one directory per skill.
    """

    STARTER_NOTES = SKILLS / "setup-personal-notes" / "starter-notes.md"
    """
    The conventions a new personal-notes file can be seeded with.
    """

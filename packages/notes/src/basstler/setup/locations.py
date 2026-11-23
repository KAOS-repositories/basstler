"""
The files and directories the personal-notes setup names.
"""

from __future__ import annotations


from basstler.locations import (
    PluginFile,
    PluginLocation,
    PluginSkillLocation,
)


class SetupPluginLocation(PluginFile):
    """
    The plugin's scripts the setup runs or names, relative to the plugin's root.
    """

    SETUP_CHECK_SCRIPT = PluginLocation.HOOKS / "check-setup.sh"
    """
    Reports, one row per prerequisite, what the personal-notes setup still lacks.
    """

    GIT_IDENTITY_SAVING_SCRIPT = PluginLocation.HOOKS / "save-git-identity.sh"
    """
    Saves the user's git identity to the personal-notes branch.
    """


class SetupPluginSkillLocation(PluginFile):
    """
    The files of the plugin's skills the setup reads, relative to the plugin's root.
    """

    STARTER_NOTES = (
        PluginSkillLocation.SKILLS / "setup-personal-notes" / "starter-notes.md"
    )
    """
    The conventions a new personal-notes file can be seeded with.
    """

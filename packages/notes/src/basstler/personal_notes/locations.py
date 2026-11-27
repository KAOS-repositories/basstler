"""
The files and directories the personal notes name.
"""

from __future__ import annotations

from basstler.locations import ProjectFile, ProjectLocation


class PersonalNotesProjectLocation(ProjectFile):
    """
    The git identities of contributors the personal-notes branch keeps.
    """

    CONTRIBUTOR_GIT_IDENTITIES = ProjectLocation.PERSONAL_NOTES / "git-identities"
    """
    The git identities of everyone else who shares the notes branch, one file per GitHub
    login.

    Mirrors ``CONTRIBUTOR_GIT_IDENTITIES_DIRECTORY`` in ``resolve-personal-notes-
    config.sh``.
    """

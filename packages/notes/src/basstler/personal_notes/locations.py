"""
The files and directories the personal notes name.
"""

from __future__ import annotations

from basstler.locations import PathEnumeration, ProjectLocation


class PersonalNotesProjectLocation(PathEnumeration):
    """
    The git identities the personal-notes branch keeps, relative to its root.
    """

    CONTRIBUTOR_GIT_IDENTITIES = ProjectLocation.PERSONAL_NOTES / "git-identities"
    """
    The git identities of everyone else who shares the notes branch, one file per GitHub
    login.

    Mirrors ``CONTRIBUTOR_GIT_IDENTITIES_DIRECTORY`` in ``resolve-personal-notes-
    config.sh``.
    """

"""
The files a release names.
"""

from __future__ import annotations

from enum import StrEnum


class ReleaseLocation(StrEnum):
    """
    A file of a release.
    """

    SETUP_SCRIPT = "release/setup.sh"
    """
    The script setting a release up.
    """

    NOTES = "release/notes.md"
    """
    The release's notes.
    """

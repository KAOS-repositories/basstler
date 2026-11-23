"""
The files a release names.
"""

from __future__ import annotations

from enum import StrEnum


class ReleaseLocation(StrEnum):
    """
    A file of a release.
    """

    NOTES = "release/notes.md"
    """
    The release's notes.
    """

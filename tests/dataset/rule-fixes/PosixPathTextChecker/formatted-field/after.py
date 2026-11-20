"""
Puts a repository path into a message through an f-string field.
"""

from __future__ import annotations

from basstler.locations import ProjectLocation


def missing_notes_line() -> str:
    """
    :return: The line saying the notes directory is missing.
    """
    return f"{ProjectLocation.PERSONAL_NOTES_DOCUMENT.parent.as_posix()} is missing"

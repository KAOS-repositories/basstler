"""
Committing.
"""

from __future__ import annotations

from tool.locations import CommitScratchFile, ProjectFile


def message_file() -> str:
    """
    :return: The file a commit message is written to.
    """
    return CommitScratchFile.MESSAGE


def readme() -> str:
    """
    :return: The project's readme.
    """
    return ProjectFile.README

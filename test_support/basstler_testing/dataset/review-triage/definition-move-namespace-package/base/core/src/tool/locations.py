"""
The files the tool names.
"""

from __future__ import annotations

from enum import StrEnum


class ProjectFile(StrEnum):
    """
    A file of the project.
    """

    README = "README.md"


class CommitScratchFile(StrEnum):
    """
    A file a commit is prepared in.
    """

    MESSAGE = "COMMIT_MESSAGE"

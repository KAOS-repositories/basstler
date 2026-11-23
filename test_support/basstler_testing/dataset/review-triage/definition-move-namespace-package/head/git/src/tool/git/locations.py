"""
The files the git commands name.
"""

from __future__ import annotations

from enum import StrEnum


class CommitScratchFile(StrEnum):
    """
    A file a commit is prepared in.
    """

    MESSAGE = "COMMIT_MESSAGE"

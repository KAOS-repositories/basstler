"""
The files and directories the git commands name.
"""

from __future__ import annotations

from pathlib import Path

from basstler.locations import PathEnumeration


class CommitScratchFile(PathEnumeration):
    """
    The files a commit built outside the working tree is staged through, relative to a
    scratch directory of its own.
    """

    INDEX = Path("index")
    """
    The index the commit's tree is staged in, leaving the clone's own untouched.
    """

    BLOB = Path("blob")
    """
    One file's content, written out to be stored as a blob.
    """

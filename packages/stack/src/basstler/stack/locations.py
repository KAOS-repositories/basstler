"""
The files and directories stack maintenance names.
"""

from __future__ import annotations

from basstler.locations import PathEnumeration, RepositoryStateLocation


class StackStateLocation(PathEnumeration):
    """
    Stack maintenance's scratch state, relative to a repository's common git directory.
    """

    BOARD = RepositoryStateLocation.DIRECTORY / "board.json"
    """
    The exported snapshot of the fork's open pull requests.
    """

    MAINTENANCE_REPORT = RepositoryStateLocation.DIRECTORY / "maintenance-report.json"
    """
    Everything the last maintenance pass did, in full.
    """

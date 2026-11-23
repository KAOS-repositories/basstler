"""
The files and directories stack maintenance names.
"""

from __future__ import annotations

from basstler.locations import RepositoryStateFile, RepositoryStateLocation


class StackStateLocation(RepositoryStateFile):
    """
    Stack maintenance's scratch state.
    """

    BOARD = RepositoryStateLocation.DIRECTORY / "board.json"
    """
    The exported snapshot of the fork's open pull requests.
    """

    MAINTENANCE_REPORT = RepositoryStateLocation.DIRECTORY / "maintenance-report.json"
    """
    Everything the last maintenance pass did, in full.
    """

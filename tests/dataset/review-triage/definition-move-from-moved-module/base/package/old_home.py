from __future__ import annotations

from enum import StrEnum


class Column(StrEnum):
    """
    A column of the board.
    """

    TODO = "todo"
    DONE = "done"


class Lane(StrEnum):
    """
    A lane of the board.
    """

    FAST = "fast"
    SLOW = "slow"


class Route(StrEnum):
    """
    Where a record is read from.
    """

    LOCAL = "local"

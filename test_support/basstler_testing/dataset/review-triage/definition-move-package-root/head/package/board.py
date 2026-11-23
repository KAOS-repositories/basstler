from __future__ import annotations

from enum import StrEnum

from .record import Record

OWNER = Record


class Column(StrEnum):
    """
    A column of the board.
    """

    TODO = "todo"

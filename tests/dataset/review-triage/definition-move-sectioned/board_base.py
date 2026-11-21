from __future__ import annotations

from enum import StrEnum

# %% the board


class Field(StrEnum):
    """
    A field of a record.
    """

    TITLE = "title"


class Priority(StrEnum):
    """
    How urgent a record is.
    """

    HIGH = "high"


class Column(StrEnum):
    """
    A column of the board.
    """

    TODO = "todo"

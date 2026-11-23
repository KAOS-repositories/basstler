from __future__ import annotations

from enum import StrEnum

from .record import Record


class Priority(StrEnum):
    """
    How urgent a record is.
    """

    HIGH = "high"

    OWNER = Record

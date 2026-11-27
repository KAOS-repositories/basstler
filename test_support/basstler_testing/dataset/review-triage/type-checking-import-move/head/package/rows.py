"""
The rows of a table.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Row:
    """
    One row.
    """

    value: int
    """
    What the row holds.
    """

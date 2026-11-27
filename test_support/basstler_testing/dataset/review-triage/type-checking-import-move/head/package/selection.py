"""
Choosing rows of a table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from package.rows import Row


def row_count(rows: list[Row]) -> int:
    """
    :param rows: Rows of a table.
    :return: How many there are.
    """
    return len(rows)

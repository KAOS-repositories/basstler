"""
Choosing rows of a table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from package.rows import Row


def first_row(rows: list[Row]) -> Row:
    """
    :param rows: Rows of a table.
    :return: The first of them.
    """
    return rows[0]


def row_count(rows: list[Row]) -> int:
    """
    :param rows: Rows of a table.
    :return: How many there are.
    """
    return len(rows)

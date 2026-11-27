"""
Picking rows of a table by their place.
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

"""
Where a store keeps its rows.
"""

from __future__ import annotations


def row_names(names: list[str]) -> list[str]:
    """
    :param names: The names of rows.
    :return: Them, sorted.
    """
    return sorted(names)

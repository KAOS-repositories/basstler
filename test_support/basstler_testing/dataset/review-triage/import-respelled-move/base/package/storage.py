"""
Where a store keeps its rows.
"""

from __future__ import annotations

from os.path import join


def row_path(name: str) -> str:
    """
    :param name: A row's name.
    :return: The file the row is kept in.
    """
    return join("rows", name)


def row_names(names: list[str]) -> list[str]:
    """
    :param names: The names of rows.
    :return: Them, sorted.
    """
    return sorted(names)

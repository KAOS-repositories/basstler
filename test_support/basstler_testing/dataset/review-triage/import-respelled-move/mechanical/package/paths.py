"""
The files rows are kept in.
"""

from __future__ import annotations

from os.path import join


def row_path(name: str) -> str:
    """
    :param name: A row's name.
    :return: The file the row is kept in.
    """
    return join("rows", name)

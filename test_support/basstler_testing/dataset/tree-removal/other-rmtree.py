"""
Calls things named ``rmtree`` that are not :func:`shutil.rmtree`.
"""

from __future__ import annotations


def rmtree(path: str) -> None:
    """
    Removes nothing.
    """


class Archive:
    """
    A thing with a method named ``rmtree``.
    """

    def rmtree(self) -> None:
        """
        Removes nothing.
        """


rmtree("clone")
Archive().rmtree()

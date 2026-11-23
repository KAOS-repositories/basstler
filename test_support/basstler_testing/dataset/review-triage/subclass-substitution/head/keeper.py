"""
Fetches a branch without naming it for a reader.
"""

from __future__ import annotations

from package.branch import Branch


def reference_of(name: str) -> str:
    """
    :param name: The branch's name.
    :return: Its remote-tracking reference.
    """
    return Branch(
        name,
        remote="origin",
    ).reference()

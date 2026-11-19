"""
Reports the branch a change goes to.
"""

from __future__ import annotations

from package.branch import Branch


def destination(name: str) -> Branch:
    """
    :param name: The branch's name.
    :return: The branch.
    """
    return Branch(name)


def report(name: str) -> str:
    """
    :param name: The branch's name.
    :return: Where the change goes.
    """
    return f"pushed to {destination(name).description}"

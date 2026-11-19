"""
Reports the branch a change goes to.
"""

from __future__ import annotations

from package.named_branch import NamedBranch


def destination(name: str) -> NamedBranch:
    """
    :param name: The branch's name.
    :return: The branch.
    """
    return NamedBranch(name)


def report(name: str) -> str:
    """
    :param name: The branch's name.
    :return: Where the change goes.
    """
    return f"pushed to {destination(name).description}"

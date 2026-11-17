"""
What the maintenance actions on a fork's pull requests have in common.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.github.repository_access import ForkPullRequests
from basstler.stack.model import Stack


@dataclass(frozen=True)
class ForkPullRequestAction:
    """
    An action that reads the derived stack and writes to its fork pull requests.
    """

    stack: Stack
    """
    The derived stack, which says which branches there are and what became of them.
    """

    fork: ForkPullRequests
    """
    The fork to read pull requests from and write them back to.
    """

"""
The pair every record about one fork pull request names: its branch and its number.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BranchPullRequest:
    """
    A fork pull request, named by its head branch and its number.
    """

    branch: str
    """
    The pull request's head branch.
    """

    pull_request_number: int
    """
    The fork pull request.
    """

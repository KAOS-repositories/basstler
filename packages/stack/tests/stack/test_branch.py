"""
Tests for a stack branch, which is a git branch.
"""

from __future__ import annotations

from basstler.git.branch import Branch
from basstler.stack.model import StackBranch

# %% the branches that are one


def test_a_stack_branch_is_a_branch() -> None:
    """
    A stack branch is a git branch.
    """
    assert issubclass(StackBranch, Branch)

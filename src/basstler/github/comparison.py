"""
How one commit relates to another, as GitHub's comparison of two refs reports it.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.json_model import ValidatedJSONModel

# %% a comparison


class ComparisonStatus(StrEnum):
    """
    How the head of a comparison relates to its base.
    """

    IDENTICAL = "identical"
    """
    They are the same commit.
    """

    AHEAD = "ahead"
    """
    The head has commits the base lacks and the base has none the head lacks.
    """

    BEHIND = "behind"
    """
    The base has commits the head lacks and the head has none the base lacks.
    """

    DIVERGED = "diverged"
    """
    Each has commits the other lacks.
    """


class Comparison(ValidatedJSONModel):
    """
    GitHub's comparison of a head with a base.
    """

    status: ComparisonStatus
    """
    How the head relates to the base.
    """

    ahead_by: int
    """
    How many commits the head has that the base lacks.
    """

    @property
    def head_is_contained_in_base(self) -> bool:
        """
        :return: Whether every commit of the head is already in the base.
        """
        return self.status in {ComparisonStatus.IDENTICAL, ComparisonStatus.BEHIND}

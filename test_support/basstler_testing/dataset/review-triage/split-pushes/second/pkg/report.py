"""
The report of the outcome.
"""

from __future__ import annotations

from pkg.scores import Outcome


def first_places(outcome: Outcome) -> str:
    """
    :param outcome: Where the searches put the confirmed table.
    :return: How many put it first, as text.
    """
    return f"{outcome.count_first_places()} times first"

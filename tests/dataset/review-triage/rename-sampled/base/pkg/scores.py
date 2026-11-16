"""
Where searches put the table a person confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Outcome:
    """
    The rank of the confirmed table in each search.
    """

    ranks: tuple[int, ...]
    """
    The confirmed table's rank in each search, counted from one.
    """

    models: tuple[str, ...] = ("large", "small")
    """
    The models compared.
    """

    def rank_of_right(self, search: int) -> int:
        """
        :param search: A search.
        :return: Where it put the confirmed table.
        """
        return self.ranks[search]

    def ranked_first(self) -> int:
        """
        :return: How many searches put the confirmed table first.
        """
        return sum(self.rank_of_right(search) == 1 for search in range(len(self.ranks)))

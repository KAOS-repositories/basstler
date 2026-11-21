"""
A class that only mentions the base class.
"""

from __future__ import annotations

from shape import Shape


class Paint:
    """
    A class unrelated to :class:`Shape`.
    """


class Colour(Paint):
    """
    Inherits from :class:`Paint`, its method taking a :class:`Shape`.
    """

    def paint(self, painted: Shape) -> None:
        """
        :param painted: What is painted.
        """

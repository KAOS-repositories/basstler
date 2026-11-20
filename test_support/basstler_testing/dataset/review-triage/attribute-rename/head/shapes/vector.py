"""
Vectors in the plane.
"""

from __future__ import annotations


class Vector:
    """
    A vector, labelled by its tag.
    """

    def __init__(self, x: float, y: float, tag: str) -> None:
        self.x = x
        self.y = y
        self.caption = tag

    def squared_length(self) -> float:
        """
        :return: The squared length; a unit vector's squared_length is one.
        """
        return self.x * self.x + self.y * self.y

    def is_unit(self) -> bool:
        """
        :return: Whether the vector is one long.
        """
        return self.squared_length() == 1.0

    @classmethod
    def described(cls, vector: Vector) -> str:
        """
        :param vector: A vector.
        :return: Its squared length, as text.
        """
        return f"{cls.squared_length(vector)}"

    @property
    def caption_text(self) -> str:
        """
        The vector's tag, in brackets.
        """
        return f"[{self.caption}]"


def total(vectors: list[Vector]) -> float:
    """
    :param vectors: Vectors.
    :return: The sum of their squared lengths.
    """
    return sum(Vector.squared_length(vector) for vector in vectors)

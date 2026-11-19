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
        self.tag = tag

    def norm_squared(self) -> float:
        """
        :return: The squared length; a unit vector's norm_squared is one.
        """
        return self.x * self.x + self.y * self.y

    def is_unit(self) -> bool:
        """
        :return: Whether the vector is one long.
        """
        return self.norm_squared() == 1.0

    @classmethod
    def described(cls, vector: Vector) -> str:
        """
        :param vector: A vector.
        :return: Its squared length, as text.
        """
        return f"{cls.norm_squared(vector)}"

    @property
    def caption_text(self) -> str:
        """
        The vector's tag, in brackets.
        """
        return f"[{self.tag}]"


def total(vectors: list[Vector]) -> float:
    """
    :param vectors: Vectors.
    :return: The sum of their squared lengths.
    """
    return sum(Vector.norm_squared(vector) for vector in vectors)

"""
Matrices, with a squared norm of their own.
"""

from __future__ import annotations


class Matrix:
    """
    A two by two matrix.
    """

    def norm_squared(self) -> float:
        """
        :return: The squared Frobenius norm.
        """
        return 4.0

    def is_zero(self) -> bool:
        """
        :return: Whether every entry is zero.
        """
        return self.norm_squared() == 0.0

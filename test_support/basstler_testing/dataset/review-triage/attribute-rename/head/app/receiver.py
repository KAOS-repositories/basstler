"""
Lengths of anything with a norm.
"""

from __future__ import annotations


def length(anything: object) -> float:
    """
    :param anything: An object with a squared norm.
    :return: Its squared norm.
    """
    return anything.squared_length()

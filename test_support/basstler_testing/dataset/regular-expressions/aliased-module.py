"""
A pattern written as text through the module imported under another name.
"""

from __future__ import annotations

import re as regular_expressions


def first_number(text):
    """
    :return: The first run of digits in *text*.
    """
    return regular_expressions.search(r"[0-9]+", text)

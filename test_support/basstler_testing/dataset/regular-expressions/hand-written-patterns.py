"""
Patterns written as regular expression text, which the pattern check reports.
"""

from __future__ import annotations

import re
from re import findall

DIGITS = re.compile(r"\d+")
"""
A pattern compiled from text.
"""


def words(text):
    """
    :return: The words in *text*, found with a pattern imported by name.
    """
    return findall(r"\w+", text)

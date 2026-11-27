"""
The state a session keeps.
"""

from __future__ import annotations

from enum import StrEnum


class SessionKey(StrEnum):
    """
    The keys a session keeps its state under.
    """

    LOADED = "loaded"
    """
    Whether every row is loaded.
    """

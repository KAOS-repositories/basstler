"""
Where records are read from.
"""

from __future__ import annotations

from enum import StrEnum

# %% the route


class Route(StrEnum):
    """
    Where a record is read from.
    """

    LOCAL = "local"

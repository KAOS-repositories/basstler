"""
The rows of a store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ROW_LIMIT: int = 1000
"""
The most rows a store holds.
"""


@dataclass
class Store:
    """
    Holds rows.
    """

    rows: list[Any] = field(default_factory=list)
    """
    The rows held.
    """

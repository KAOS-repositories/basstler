"""
The rows of a store and how they are read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Store:
    """
    Holds rows.
    """

    rows: list[Any] = field(default_factory=list)
    """
    The rows held.
    """

"""
Gives a repository's location as a file URL built by putting its path after
``file://``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Repository:
    """
    A repository on disk.
    """

    path: Path
    """
    The repository's directory.
    """

    @property
    def url(self) -> str:
        """
        The repository's location as a file URL.
        """
        return f"file://{self.path}"

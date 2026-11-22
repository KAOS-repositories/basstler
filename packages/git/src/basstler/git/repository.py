"""
A git repository, the owner every branch belongs to.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# %% the repository


class GitRepository(ABC):
    """
    A git repository, which every branch belongs to.
    """

    @property
    @abstractmethod
    def url(self) -> str:
        """
        The URL the repository is fetched from and pushed to.
        """

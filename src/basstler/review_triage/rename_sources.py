"""
The interface of everything that finds or rules out a pull request's renames.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from basstler.class_property import classproperty
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.renames import RenameDecisions

# %% rename sources


@dataclass(frozen=True)
class RenameSource(ABC):
    """
    Finds renames a pull request makes throughout, or rules out ones an earlier source
    found.
    """

    @classproperty
    @abstractmethod
    def label(cls) -> str:
        """
        What a report says found a rename this source accepts.
        """

    @classproperty
    def finds_moves(cls) -> bool:
        """
        Whether the renames this source accepts move code to another place, which leaves
        no name for a reviewer to judge.
        """
        return False

    @abstractmethod
    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        """
        :param changes: The pull request and the files it changes.
        :return: The renames this source accepts and those it rejects.
        """

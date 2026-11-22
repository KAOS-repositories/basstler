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

    @abstractmethod
    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        """
        :param changes: The pull request and the files it changes.
        :return: The renames this source accepts and those it rejects.
        """

"""
A set of rules a distribution adds to the rules a project is held to.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from basstler.playbook.component import PlaybookComponent


@dataclass(frozen=True)
class Ruleset[RuleType](PlaybookComponent, ABC):
    """
    Rules of one kind that a project is held to; each kind of rule binds
    ``RuleType`` in a subclass of its own.
    """

    @property
    @abstractmethod
    def rules(self) -> tuple[RuleType, ...]:
        """
        The rules, in the order they are listed.
        """

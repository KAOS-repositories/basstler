"""
What other distributions do once a maintenance pass has closed fork pull requests whose
work landed upstream.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from importlib.metadata import entry_points

from basstler.maintenance.landed_closing import ClosedAsLanded

# %% registration


class EntryPointGroup(StrEnum):
    """
    The entry point groups an installed distribution registers maintenance work under.
    """

    LANDED_CLOSING_FOLLOW_UPS = "basstler.landed_closing_follow_ups"
    """
    Each entry names a :class:`LandedClosingFollowUp` subclass.
    """


# %% follow-ups


class LandedClosingFollowUp(ABC):
    """
    Work a distribution above the stack does once a pass has closed pull requests whose
    work landed; a registered subclass is constructed with no arguments.
    """

    @abstractmethod
    def respond_to_closing(self, closed: Sequence[ClosedAsLanded]) -> str | None:
        """
        :param closed: The pull requests the pass closed, never empty.
        :return: What became of the work, for the finish summary; ``None`` when there
            was nothing to do.
        """


@dataclass(frozen=True)
class LandedClosingFollowUps:
    """
    The follow-ups one pass runs after closing landed pull requests.
    """

    follow_ups: tuple[LandedClosingFollowUp, ...] = ()
    """
    Run in this order.
    """

    @classmethod
    def installed(cls) -> LandedClosingFollowUps:
        """
        :return: One of each follow-up registered under
            :attr:`EntryPointGroup.LANDED_CLOSING_FOLLOW_UPS`, in the order of their
            entry point names.
        """
        registered = entry_points(group=EntryPointGroup.LANDED_CLOSING_FOLLOW_UPS)
        return cls(
            tuple(
                entry.load()()
                for entry in sorted(registered, key=lambda entry: entry.name)
            )
        )

    def respond_to_closing(self, closed: Sequence[ClosedAsLanded]) -> tuple[str, ...]:
        """
        :param closed: The pull requests the pass closed.
        :return: What became of each follow-up that had something to do; empty, with
            none run, when nothing was closed.
        """
        if not closed:
            return ()
        outcomes = (
            follow_up.respond_to_closing(closed) for follow_up in self.follow_ups
        )
        return tuple(outcome for outcome in outcomes if outcome is not None)

"""
The plan page's button that copies the command offering the plan to another person.
"""

from __future__ import annotations

from dataclasses import dataclass

from basstler.github.repository import Repository
from basstler.plan.handover_options import PlanHandoverCommand

# %% the button


@dataclass(frozen=True)
class HandoverButton:
    """
    Copies :attr:`command` with the receiver typed beside the button, run in a checkout
    of the plan's repository.
    """

    plan_identifiers: tuple[str, ...]
    """
    The plan, then every plan it depends on, which an offer has to name together.
    """

    plan_repository: Repository
    """
    The plan's default repository, whose name a receiver's fork is assumed to keep.
    """

    @property
    def command(self) -> str:
        """
        The offer, short of the options naming the receiver.
        """
        return " ".join([PlanHandoverCommand.OFFER.invocation, *self.plan_identifiers])

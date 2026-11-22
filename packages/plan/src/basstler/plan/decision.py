"""
The decisions a plan item asks of its owner, and the options that answer each.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# %% the options


class ExperimentVerdict(StrEnum):
    """
    How an experiment ends, as the ``/plan-experiment-verdict`` skill is told.
    """

    ACCEPT = "accept"
    """
    The experiment is split into the pull requests that land it.
    """

    ITERATE = "iterate"
    """
    The experiment goes on with the changes its owner asks for.
    """

    DROP = "drop"
    """
    The experiment is abandoned.
    """


@dataclass(frozen=True)
class DecisionOption:
    """
    One way the owner can answer a decision: a button that copies the skill command
    carrying it out.
    """

    label: str
    """
    What the button is called.
    """

    skill_command_name: str
    """
    The skill that carries the option out, as a session types it.
    """

    argument: str
    """
    What the skill is told the owner chose.
    """

    asks_for_request: bool
    """
    Whether the option cannot be carried out without the owner's own words.
    """

    def invocation(self, plan_id: str, item_identifier: str) -> str:
        """
        :param plan_id: The plan holding the decided item.
        :param item_identifier: The decided item.
        :return: The whole skill command, without the owner's request.
        """
        return f"{self.skill_command_name} {plan_id}/{item_identifier} {self.argument}"


# %% the decisions


class Decision(StrEnum):
    """
    What an owner's item asks its owner to decide.
    """

    EXPERIMENT_VERDICT = "experiment-verdict"
    """
    Whether an experiment is accepted and split, kept iterating, or dropped.
    """

    @property
    def options(self) -> tuple[DecisionOption, ...]:
        """
        The ways the owner can answer, in the order they are offered.
        """
        match self:
            case Decision.EXPERIMENT_VERDICT:
                skill = "/plan-experiment-verdict"
                return (
                    DecisionOption(
                        "Accept & split", skill, ExperimentVerdict.ACCEPT, False
                    ),
                    DecisionOption(
                        "Keep iterating", skill, ExperimentVerdict.ITERATE, True
                    ),
                    DecisionOption("Drop", skill, ExperimentVerdict.DROP, False),
                )

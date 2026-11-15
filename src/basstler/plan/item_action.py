"""
What a not-done plan item calls for next: the skill that starts or resolves it, and the
command that invokes it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from basstler.class_property import classproperty
from basstler.plan.model import ItemStatus
from basstler.plan.model_alias import ModelAlias
from basstler.plan.structure import Item

# %% labels


class ActionLabel(StrEnum):
    """
    What an action is called where it is offered, one per item status it answers.
    """

    START_NOW = "Start now"
    """
    A not-started item whose dependencies are ready to build on.
    """

    RESOLVE = "Resolve"
    """
    A blocked item.
    """

    RESUME = "Resume"
    """
    An item in progress.
    """

    RECONSIDER = "Reconsider"
    """
    A deferred item.
    """


# %% actions


@dataclass(frozen=True)
class ItemAction(ABC):
    """
    The next action of one not-done item, routed to the skill that carries it out.
    """

    label: ActionLabel
    """
    What the action is called where it is offered.
    """

    plan_id: str
    """
    The plan this action's command targets.
    """

    item_identifier: str
    """
    The item this action's command targets.
    """

    recommended_model: ModelAlias | None = None
    """
    The model suited to the item, or ``None`` when none was recommended.
    """

    @classproperty
    @abstractmethod
    def skill_command_name(cls) -> str:
        """
        The skill this action invokes, as a session types it.
        """

    @property
    def command(self) -> str:
        """
        The whole command a session is given to carry the action out.
        """
        return f"{self.skill_command_name} {self.plan_id} {self.item_identifier}"

    @classmethod
    def from_item_state(
        cls, plan_id: str, item: Item, dependencies_are_ready: bool
    ) -> ItemAction | None:
        """
        :param plan_id: The plan holding the item.
        :param item: The item to act on.
        :param dependencies_are_ready: Whether each of its dependencies can be built on.
        :return: The item's next action; ``None`` for a done item, for one its owner
            performs, and for a not-started one until its dependencies are ready.
        """
        if item.is_performed_by_owner:
            return None
        match item.status:
            case ItemStatus.DONE:
                return None
            case ItemStatus.NOT_STARTED:
                if not dependencies_are_ready:
                    return None
                return StartNowAction.starting(plan_id, item)
            case ItemStatus.BLOCKED:
                label = ActionLabel.RESOLVE
            case ItemStatus.IN_PROGRESS:
                label = ActionLabel.RESUME
            case ItemStatus.DEFERRED:
                label = ActionLabel.RECONSIDER
        return ResolveAction(
            label=label,
            plan_id=plan_id,
            item_identifier=item.identifier,
            recommended_model=item.recommended_model,
        )


@dataclass(frozen=True)
class StartNowAction(ItemAction):
    """
    Starts a not-started item whose dependencies are ready.
    """

    @classproperty
    def skill_command_name(cls) -> str:
        return "/plan-item-kickoff"

    @classmethod
    def starting(cls, plan_id: str, item: Item) -> StartNowAction:
        """
        :param plan_id: The plan holding the item.
        :param item: The item to start.
        :return: The action that starts it.
        """
        return cls(
            label=ActionLabel.START_NOW,
            plan_id=plan_id,
            item_identifier=item.identifier,
            recommended_model=item.recommended_model,
        )


@dataclass(frozen=True)
class ResolveAction(ItemAction):
    """
    Resolves a blocked, in-progress or deferred item on its existing branch.
    """

    @classproperty
    def skill_command_name(cls) -> str:
        return "/plan-item-resolve"

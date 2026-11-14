"""
Actions that change a module or a source tree and know their exact inverse, and plans
composing them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import libcst
from libcst.metadata import CodeRange

from basstler.code_modification.exceptions import ActionTargetMissingError
from basstler.code_modification.positions import PositionedModule

# %% actions


class Action[Target](ABC):
    """
    A change to a target that can be undone exactly.
    """

    @abstractmethod
    def apply(self, target: Target) -> AppliedAction[Target]:
        """
        :param target: The target to change, which is left as it is.
        :return: The changed target, and the action that turns it back into *target*.
        :raises ActionTargetMissingError: If *target* lacks what the action changes.
        """


@dataclass(frozen=True)
class AppliedAction[Target]:
    """
    The outcome of applying an action.
    """

    result: Target
    """
    The changed target.
    """

    inverse: Action[Target]
    """
    The action that turns :attr:`result` back into the target the action was applied to.
    """


@dataclass(frozen=True)
class NodeReplacement(Action[libcst.Module]):
    """
    Replaces the node at one location by another.
    """

    location: CodeRange
    """
    The code range of :attr:`original` in the module the action is applied to.
    """

    original: libcst.CSTNode
    """
    The node replaced, which the module must hold at :attr:`location`.
    """

    replacement: libcst.CSTNode
    """
    The node put in its place.
    """

    def apply(self, target: libcst.Module) -> AppliedAction[libcst.Module]:
        positions = PositionedModule(target).positions
        original = next(
            (
                node
                for node, code_range in positions.items()
                if code_range == self.location and node.deep_equals(self.original)
            ),
            None,
        )
        if original is None:
            raise ActionTargetMissingError(self.location, type(self.original).__name__)
        replaced = libcst.ensure_type(
            target.deep_replace(original, self.replacement), libcst.Module
        )
        replacement_location = PositionedModule(replaced).positions[self.replacement]
        return AppliedAction(
            replaced,
            NodeReplacement(replacement_location, self.replacement, self.original),
        )


# %% plans


@dataclass(frozen=True)
class ActionPlan[Target](Action[Target]):
    """
    Actions applied in order, each to the target the one before it produced, and undone
    in the reverse order.
    """

    actions: tuple[Action[Target], ...] = ()
    """
    The actions, in the order they are applied.
    """

    def apply(self, target: Target) -> AppliedAction[Target]:
        inverses: list[Action[Target]] = []
        for action in self.actions:
            applied = action.apply(target)
            target = applied.result
            inverses.append(applied.inverse)
        return AppliedAction(target, ActionPlan(tuple(reversed(inverses))))

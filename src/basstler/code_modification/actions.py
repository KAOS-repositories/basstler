"""
Actions that change a module and know their exact inverse, and plans composing them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import libcst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor
from libcst.metadata import CodeRange

from basstler.code_modification.exceptions import ActionTargetMissingError
from basstler.code_modification.positions import PositionedModule

# %% actions


class Action(ABC):
    """
    A change to a module that can be undone exactly.
    """

    @abstractmethod
    def apply(self, module: libcst.Module) -> AppliedAction:
        """
        :param module: The module to change, which is left as it is.
        :return: The changed module, and the action that turns it back into *module*.
        :raises ActionTargetMissingError: If *module* lacks what the action changes.
        """


@dataclass(frozen=True)
class AppliedAction:
    """
    The outcome of applying an action.
    """

    module: libcst.Module
    """
    The changed module.
    """

    inverse: Action
    """
    The action that turns :attr:`module` back into the module the action was applied to.
    """


@dataclass(frozen=True)
class NodeReplacement(Action):
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

    def apply(self, module: libcst.Module) -> AppliedAction:
        positions = PositionedModule(module).positions
        target = next(
            (
                node
                for node, code_range in positions.items()
                if code_range == self.location and node.deep_equals(self.original)
            ),
            None,
        )
        if target is None:
            raise ActionTargetMissingError(self.location, type(self.original).__name__)
        replaced = libcst.ensure_type(
            module.deep_replace(target, self.replacement), libcst.Module
        )
        replacement_location = PositionedModule(replaced).positions[self.replacement]
        return AppliedAction(
            replaced,
            NodeReplacement(replacement_location, self.replacement, self.original),
        )


# %% imports


class ModuleTransformation(Action, ABC):
    """
    Changes a whole module, which the action that restores the module undoes.
    """

    @abstractmethod
    def transform(self, module: libcst.Module) -> libcst.Module:
        """
        :param module: The module the action is applied to.
        :return: The module with the change made.
        """

    def apply(self, module: libcst.Module) -> AppliedAction:
        return AppliedAction(self.transform(module), ModuleReplacement(module))


@dataclass(frozen=True)
class ModuleReplacement(ModuleTransformation):
    """
    Replaces a module with another one.
    """

    replacement: libcst.Module
    """
    The module that takes the place of the one the action is applied to.
    """

    def transform(self, module: libcst.Module) -> libcst.Module:
        return self.replacement


@dataclass(frozen=True)
class ImportInsertion(ModuleTransformation):
    """
    Imports a class in a module, merged into an import of its module where there is one
    and left out where the module imports the class already.
    """

    imported: type
    """
    The class to import.
    """

    def transform(self, module: libcst.Module) -> libcst.Module:
        context = CodemodContext()
        AddImportsVisitor.add_needed_import(
            context, self.imported.__module__, self.imported.__name__
        )
        return AddImportsVisitor(context).transform_module(module)


# %% plans


@dataclass(frozen=True)
class ActionPlan(Action):
    """
    Actions applied in order, each to the module the one before it produced, and undone
    in the reverse order.
    """

    actions: tuple[Action, ...] = ()
    """
    The actions, in the order they are applied.
    """

    def apply(self, module: libcst.Module) -> AppliedAction:
        inverses: list[Action] = []
        for action in self.actions:
            applied = action.apply(module)
            module = applied.module
            inverses.append(applied.inverse)
        return AppliedAction(module, ActionPlan(tuple(reversed(inverses))))

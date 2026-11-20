"""
Actions that change a module or a source tree and know their exact inverse, and plans
composing them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

import libcst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor
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
        return NodeReplacements((self,)).apply(target)

    def target_in(
        self, positions: Mapping[libcst.CSTNode, CodeRange]
    ) -> libcst.CSTNode:
        """
        :param positions: The code range of each node of a module.
        :return: The node of that module the replacement replaces.
        :raises ActionTargetMissingError: If the module lacks :attr:`original` at
            :attr:`location`.
        """
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
        return original


@dataclass(frozen=True)
class NodeReplacements(Action[libcst.Module]):
    """
    Makes replacements whose locations do not overlap, all in one pass over the module.
    """

    replacements: tuple[NodeReplacement, ...]
    """
    The replacements, each located in the module the action is applied to.
    """

    def apply(self, target: libcst.Module) -> AppliedAction[libcst.Module]:
        positions = PositionedModule(target).positions
        substitution = NodeSubstitution(
            {
                replacement.target_in(positions): replacement.replacement
                for replacement in self.replacements
            }
        )
        replaced = libcst.ensure_type(target.visit(substitution), libcst.Module)
        replaced_positions = PositionedModule(replaced).positions
        return AppliedAction(
            replaced,
            NodeReplacements(
                tuple(
                    NodeReplacement(
                        replaced_positions[replacement.replacement],
                        replacement.replacement,
                        replacement.original,
                    )
                    for replacement in self.replacements
                )
            ),
        )


@dataclass
class NodeSubstitution(libcst.CSTTransformer):
    """
    Puts a node in the place of each node of a module it is given one for.
    """

    substitutes: Mapping[libcst.CSTNode, libcst.CSTNode]
    """
    The node to put in the place of each node, which is identified by identity.
    """

    def __post_init__(self) -> None:
        """
        Initialise the transformer, which the dataclass's generated initialiser skips.
        """
        super().__init__()

    def on_leave(
        self, original_node: libcst.CSTNode, updated_node: libcst.CSTNode
    ) -> libcst.CSTNode:
        """
        :param original_node: A node of the module visited.
        :param updated_node: That node with its children substituted.
        :return: The substitute of *original_node*, else *updated_node*.
        """
        return self.substitutes.get(original_node, updated_node)


# %% imports


class ModuleTransformation(Action[libcst.Module], ABC):
    """
    Changes a whole module, which the action that restores the module undoes.
    """

    @abstractmethod
    def transform(self, module: libcst.Module) -> libcst.Module:
        """
        :param module: The module the action is applied to.
        :return: The module with the change made.
        """

    def apply(self, target: libcst.Module) -> AppliedAction[libcst.Module]:
        return AppliedAction(self.transform(target), ModuleReplacement(target))


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


class PlanBuilder[Target](ABC):
    """
    Builds the action that changes a target, from the target itself.
    """

    @abstractmethod
    def build(self, target: Target) -> Action[Target]:
        """
        :param target: What the action is to change.
        :return: The action, to be applied to *target*.
        """

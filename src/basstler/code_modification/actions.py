"""
Actions that change a module and know their exact inverse, and plans composing them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import libcst
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


# %% statements


@dataclass(frozen=True)
class StatementRemoval(Action):
    """
    Removes a statement from the top level of a module.
    """

    statement: libcst.SimpleStatementLine
    """
    The statement removed, which the module must hold at its top level.
    """

    def apply(self, module: libcst.Module) -> AppliedAction:
        index = next(
            (
                position
                for position, candidate in enumerate(module.body)
                if candidate.deep_equals(self.statement)
            ),
            None,
        )
        if index is None:
            raise ActionTargetMissingError(
                PositionedModule(module).positions[module.body[0]],
                type(self.statement).__name__,
            )
        body = [*module.body[:index], *module.body[index + 1 :]]
        return AppliedAction(
            module.with_changes(body=body), StatementInsertion(index, self.statement)
        )


@dataclass(frozen=True)
class StatementInsertion(Action):
    """
    Puts a statement at one position of a module's top level.
    """

    index: int
    """
    The position of the statement among the module's top-level statements.
    """

    statement: libcst.SimpleStatementLine
    """
    The statement inserted.
    """

    def apply(self, module: libcst.Module) -> AppliedAction:
        body = [*module.body[: self.index], self.statement, *module.body[self.index :]]
        return AppliedAction(
            module.with_changes(body=body), StatementRemoval(self.statement)
        )


@dataclass(frozen=True)
class ImportInsertion(Action):
    """
    Imports a name in a module that does not import it yet, after the module's last
    import.
    """

    statement: libcst.SimpleStatementLine
    """
    The import statement.
    """

    def apply(self, module: libcst.Module) -> AppliedAction:
        if any(candidate.deep_equals(self.statement) for candidate in module.body):
            return AppliedAction(module, ActionPlan())
        return StatementInsertion(self.insertion_index(module), self.statement).apply(
            module
        )

    @staticmethod
    def insertion_index(module: libcst.Module) -> int:
        """
        :return: The position after the module's last import, or after its docstring
            where it imports nothing.
        """
        last_import = max(
            (
                position
                for position, candidate in enumerate(module.body)
                if isinstance(candidate, libcst.SimpleStatementLine)
                and isinstance(candidate.body[0], libcst.Import | libcst.ImportFrom)
            ),
            default=None,
        )
        if last_import is not None:
            return last_import + 1
        return 1 if module.get_docstring(clean=False) is not None else 0


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

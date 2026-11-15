"""
The import a change to a module needs, added where the module keeps its imports.
"""

from __future__ import annotations

from dataclasses import dataclass

import libcst
from libcst.helpers import get_full_name_for_node

from basstler.code_modification.actions import Action, ActionPlan, StatementInsertion

# %% the import


@dataclass(frozen=True)
class ImportedName:
    """
    A name a module imports from another module, as ``from module import name``.
    """

    module_name: str
    """
    The dotted name of the module the name comes from.
    """

    name: str
    """
    The name imported.
    """

    def addition_to(self, module: libcst.Module) -> Action:
        """
        :param module: The module that needs the import.
        :return: The action importing the name below the last import of *module*, below
            its docstring when it has no import; an empty plan when it imports the name
            already.
        """
        statements = [
            statement
            for line in module.body
            if isinstance(line, libcst.SimpleStatementLine)
            for statement in line.body
        ]
        if any(self.is_imported_by(statement) for statement in statements):
            return ActionPlan()
        imports = [
            index
            for index, line in enumerate(module.body)
            if isinstance(line, libcst.SimpleStatementLine)
            and isinstance(line.body[0], libcst.Import | libcst.ImportFrom)
        ]
        index = imports[-1] + 1 if imports else int(module.get_docstring() is not None)
        return StatementInsertion(
            index,
            libcst.parse_statement(f"from {self.module_name} import {self.name}"),
        )

    def is_imported_by(self, statement: libcst.BaseSmallStatement) -> bool:
        """
        :return: Whether *statement* imports :attr:`name` from :attr:`module_name`
            under its own name.
        """
        if not isinstance(statement, libcst.ImportFrom) or statement.module is None:
            return False
        if isinstance(statement.names, libcst.ImportStar):
            return False
        return (
            statement.relative == ()
            and get_full_name_for_node(statement.module) == self.module_name
            and any(
                isinstance(alias.name, libcst.Name)
                and alias.name.value == self.name
                and alias.asname is None
                for alias in statement.names
            )
        )

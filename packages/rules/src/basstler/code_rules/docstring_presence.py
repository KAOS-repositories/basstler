"""
Finds modules, classes, functions and fields that have no docstring.
"""

from __future__ import annotations

import abc
import importlib
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from types import ModuleType
from typing import override

import libcst

from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.syntax import BodySyntax
from basstler.code_rules.checker import CodeRuleViolation
from basstler.code_rules.syntax_tree_checker import SyntaxTreeChecker

# %% what is documented


class DocumentedKind(StrEnum):
    """
    The kinds of code that carry a docstring.
    """

    MODULE = "module"
    """
    A whole source file.
    """

    CLASS = "class"
    """
    A class definition.
    """

    FUNCTION = "function"
    """
    A function or method definition.
    """

    FIELD = "field"
    """
    An annotated assignment in a class body.
    """


@dataclass(frozen=True)
class ImportedModule:
    """
    A source file as the module Python imports it, which tells whether a method
    implements an abstract method of a base class.
    """

    path: Path
    """
    The source file of the module.
    """

    @cached_property
    def module(self) -> ModuleType | None:
        """
        The module imported from :attr:`path`; none when it cannot be imported.
        """
        source = self.path.resolve()
        root = source.parent
        while (root / "__init__.py").is_file():
            root = root.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        name = ".".join(source.relative_to(root).with_suffix("").parts)
        try:
            module = importlib.import_module(name.removesuffix(".__init__"))
        except Exception:
            # Handle unimportable modules gracefully: whatever the import raises, only
            # the methods of this module go unchecked.
            return None
        if module.__file__ is None or Path(module.__file__).resolve() != source:
            return None
        return module

    def class_named(self, scope: tuple[str, ...] | None) -> type | None:
        """
        :param scope: The names of a class and the classes enclosing it; none for a
            class defined inside a function.
        :return: The class; none when it cannot be found.
        """
        if scope is None or self.module is None:
            return None
        found: ModuleType | type | None = self.module
        for name in scope:
            found = vars(found).get(name)
            if not isinstance(found, type):
                return None
        return found

    def implements_abstract_method(
        self, scope: tuple[str, ...] | None, method_name: str
    ) -> bool:
        """
        :param scope: The names of a class and the classes enclosing it.
        :param method_name: The name of a method of the class.
        :return: Whether the first base class defining *method_name* leaves it abstract.
        """
        for base in self.class_named(scope).__mro__[1:]:
            if method_name in vars(base):
                return (
                    isinstance(base, abc.ABCMeta)
                    and method_name in base.__abstractmethods__
                )
        return False


# %% the check


@dataclass(frozen=True)
class MissingDocstringChecker(SyntaxTreeChecker):
    """
    Finds undocumented code; a method implementing an abstract method inherits its
    base's docstring and needs none of its own.
    """

    @override
    def violations_of_module(
        self, path: Path, module: PositionedModule
    ) -> Iterator[CodeRuleViolation]:
        if module.module.body and module.module.get_docstring(clean=False) is None:
            last_line = module.positions[module.module.body[-1]].end.line
            yield self.violation(path, DocumentedKind.MODULE, 1, last_line)
        yield from self.undocumented_definitions(
            path, module, module.module, (), ImportedModule(path)
        )

    def undocumented_definitions(
        self,
        path: Path,
        module: PositionedModule,
        parent: libcst.CSTNode,
        scope: tuple[str, ...] | None,
        imported: ImportedModule,
        methods: frozenset[libcst.CSTNode] = frozenset(),
    ) -> Iterator[CodeRuleViolation]:
        """
        :param module: The module of *path*.
        :param parent: A node whose descendants are checked.
        :param scope: The names of the classes enclosing *parent*; none inside a
            function, where a class cannot be looked up.
        :param imported: The module of *path* as Python imports it.
        :param methods: The functions defined directly in the body of the class
            enclosing *parent*.
        :return: A violation for every undocumented class, function and field below
            *parent*. A method is skipped when its class cannot be looked up, and
            when it implements an abstract method, whose docstring suffices.
        """
        for node in parent.children:
            if isinstance(node, libcst.ClassDef):
                yield from self.undocumented_fields(path, module, node)
                if node.get_docstring(clean=False) is None:
                    yield self.definition_violation(
                        path, module, DocumentedKind.CLASS, node
                    )
                class_scope = None if scope is None else (*scope, node.name.value)
                members = frozenset(
                    statement
                    for statement in BodySyntax(node.body).statements
                    if isinstance(statement, libcst.FunctionDef)
                )
                yield from self.undocumented_definitions(
                    path, module, node, class_scope, imported, members
                )
                continue
            if not isinstance(node, libcst.FunctionDef):
                yield from self.undocumented_definitions(
                    path, module, node, scope, imported, methods
                )
                continue
            if node.get_docstring(clean=False) is None and not self.is_exempt_method(
                methods, scope, node, imported
            ):
                yield self.definition_violation(
                    path, module, DocumentedKind.FUNCTION, node
                )
            yield from self.undocumented_definitions(path, module, node, None, imported)

    @staticmethod
    def is_exempt_method(
        methods: frozenset[libcst.CSTNode],
        scope: tuple[str, ...] | None,
        node: libcst.FunctionDef,
        imported: ImportedModule,
    ) -> bool:
        """
        :return: Whether *node* is a method that needs no docstring of its own: its class
            cannot be looked up, or it implements an abstract method.
        """
        if node not in methods:
            return False
        if imported.class_named(scope) is None:
            return True
        return imported.implements_abstract_method(scope, node.name.value)

    def undocumented_fields(
        self, path: Path, module: PositionedModule, definition: libcst.ClassDef
    ) -> Iterator[CodeRuleViolation]:
        """
        :return: A violation for every annotated assignment in *definition*'s body that no
            string literal directly follows.
        """
        statements = BodySyntax(definition.body).statements
        for index, statement in enumerate(statements):
            if not isinstance(statement, libcst.AnnAssign):
                continue
            following = statements[index + 1 : index + 2]
            if following and BodySyntax.is_string(following[0]):
                continue
            location = module.positions[statement]
            yield self.violation(
                path, DocumentedKind.FIELD, location.start.line, location.end.line
            )

    def definition_violation(
        self,
        path: Path,
        module: PositionedModule,
        kind: DocumentedKind,
        definition: libcst.ClassDef | libcst.FunctionDef,
    ) -> CodeRuleViolation:
        """
        :return: The violation of the undocumented class or function *definition*,
            starting at its first decorator, else at its keyword.
        """
        decorators = definition.decorators
        first = module.positions[decorators[0] if decorators else definition]
        return self.violation(
            path, kind, first.start.line, module.positions[definition].end.line
        )

    @staticmethod
    def violation(
        path: Path, kind: DocumentedKind, first_line: int, last_line: int
    ) -> CodeRuleViolation:
        """
        :return: The violation of the undocumented *kind* of code spanning *first_line* to
            *last_line* of *path*.
        """
        return CodeRuleViolation(
            path, first_line, last_line, f"{kind} has no docstring; add one"
        )

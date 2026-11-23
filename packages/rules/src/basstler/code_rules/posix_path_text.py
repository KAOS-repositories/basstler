"""
Finds paths turned into text with :class:`str`, an f-string field or
:func:`os.path.relpath`, which write ``\\`` on Windows, and fixes them to
:meth:`pathlib.PurePath.as_posix`.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cached_property
from pathlib import Path, PurePath
from typing import override

import libcst
from libcst import matchers
from libcst.helpers import get_full_name_for_node

from basstler.class_property import classproperty
from basstler.code_modification.patterns import CodePattern
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_file import EditablePythonSourceFile
from basstler.code_modification.specification import Specification
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
)
from basstler.locations import PathEnumeration

RELATIVE_PATH_FUNCTION = f"{os.__name__}.path.{os.path.relpath.__name__}"
"""
The full name of the function computing a relative path as text.
"""

PATH_CLASSES = frozenset({Path.__name__, PurePath.__name__})
"""
The :mod:`pathlib` classes whose call gives a path.
"""

PATH_METHODS = frozenset(
    {
        PurePath.with_name.__name__,
        PurePath.with_suffix.__name__,
        PurePath.relative_to.__name__,
        Path.resolve.__name__,
        Path.absolute.__name__,
    }
)
"""
The methods of a path that return a path.
"""

PARENT_ATTRIBUTE = "parent"
"""
The attribute of a path holding the path of its directory.
"""

# %% the path enumerations a module binds


@dataclass(frozen=True)
class ModuleSource:
    """
    A Python source file of an importable package, read without importing it.
    """

    path: Path
    """
    The file.
    """

    @cached_property
    def module(self) -> libcst.Module:
        """
        The file's syntax tree.
        """
        return EditablePythonSourceFile(self.path).parse()

    @staticmethod
    def of_module(dotted_name: str) -> ModuleSource | None:
        """
        :param dotted_name: The absolute name of a module.
        :return: Its source, ``None`` unless it is a source file inside a package
            importable here.
        """
        package, *submodules = dotted_name.split(".")
        if not submodules:
            return None
        specification = importlib.util.find_spec(package)
        if specification is None or not specification.submodule_search_locations:
            return None
        for location in specification.submodule_search_locations:
            base = Path(location).joinpath(*submodules)
            for candidate in (base.with_suffix(".py"), base / "__init__.py"):
                if candidate.is_file():
                    return ModuleSource(candidate)
        return None


@dataclass(frozen=True)
class PathEnumerationFinder:
    """
    Finds the names a module binds to a :class:`~basstler.locations.PathEnumeration`
    subclass it defines or imports by absolute name, reading each module once.
    """

    found: dict[str, frozenset[str]] = field(default_factory=dict, compare=False)
    """
    The names found in each module read, by the module's absolute name.
    """

    def names_in(self, module: libcst.Module) -> frozenset[str]:
        """
        :return: The names *module* binds to a path enumeration class.
        """
        names: set[str] = set()
        for statement in module.body:
            if isinstance(statement, libcst.ClassDef):
                if any(
                    get_full_name_for_node(base.value)
                    in {PathEnumeration.__name__, *names}
                    for base in statement.bases
                ):
                    names.add(statement.name.value)
                continue
            if isinstance(statement, libcst.SimpleStatementLine):
                for small in statement.body:
                    if isinstance(small, libcst.ImportFrom):
                        names |= self.imported_names(small)
        return frozenset(names)

    def imported_names(self, statement: libcst.ImportFrom) -> set[str]:
        """
        :return: The names *statement* binds to a path enumeration class; none for a
            relative or star import.
        """
        if (
            statement.relative
            or statement.module is None
            or isinstance(statement.names, libcst.ImportStar)
        ):
            return set()
        dotted_name = get_full_name_for_node(statement.module)
        if dotted_name not in self.found:
            self.found[dotted_name] = frozenset()
            source = ModuleSource.of_module(dotted_name)
            if source is not None:
                self.found[dotted_name] = self.names_in(source.module)
        return {
            alias.evaluated_alias or alias.evaluated_name
            for alias in statement.names
            if alias.evaluated_name in self.found[dotted_name]
        }


@dataclass(frozen=True)
class PathExpressions:
    """
    Tells the expressions of one module that certainly give a path.
    """

    enumeration_names: frozenset[str]
    """
    The names the module binds to a path enumeration class.
    """

    def gives_path(self, expression: libcst.BaseExpression) -> bool:
        """
        :return: Whether *expression* is a member of a path enumeration, a call of a
            :mod:`pathlib` class, or built from a path by ``/``, its parent or one of
            :data:`PATH_METHODS`.
        """
        if isinstance(expression, libcst.BinaryOperation):
            return isinstance(expression.operator, libcst.Divide) and self.gives_path(
                expression.left
            )
        if isinstance(expression, libcst.Attribute):
            if expression.attr.value == PARENT_ATTRIBUTE:
                return self.gives_path(expression.value)
            return get_full_name_for_node(expression.value) in self.enumeration_names
        if not isinstance(expression, libcst.Call):
            return False
        function = expression.func
        if isinstance(function, libcst.Attribute) and (
            function.attr.value in PATH_METHODS
        ):
            return self.gives_path(function.value)
        return get_full_name_for_node(function) in {
            *PATH_CLASSES,
            *(f"{pathlib.__name__}.{name}" for name in PATH_CLASSES),
        }


# %% the places


class PathTextShape(Enum):
    """
    How a place turns a path into text.
    """

    STRING_CONVERSION = auto()
    """
    It passes the path to :class:`str`.
    """

    FORMATTED_FIELD = auto()
    """
    It interpolates the path in an f-string field.
    """

    RELATIVE_PATH = auto()
    """
    It computes a relative path with :func:`os.path.relpath`, which returns text.
    """


@dataclass(frozen=True)
class PathText(Specification):
    """
    A place turning a path into text.
    """

    path: libcst.BaseExpression
    """
    The expression giving the path, or the :func:`os.path.relpath` call.
    """

    shape: PathTextShape
    """
    How the place turns the path into text.
    """


class RelativePathCall(CodePattern):
    """
    A call of :func:`os.path.relpath`.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        return matchers.Call(
            func=matchers.MatchIfTrue(
                lambda function: (
                    get_full_name_for_node(function) == RELATIVE_PATH_FUNCTION
                )
            )
        )


class WrappedRelativePath(CodePattern):
    """
    A :mod:`pathlib` class called on the text :func:`os.path.relpath` returns.
    """

    @classproperty
    def matcher(cls) -> matchers.Call:
        return matchers.Call(
            func=matchers.MatchIfTrue(
                lambda function: get_full_name_for_node(function) in PATH_CLASSES
            ),
            args=[matchers.Arg(value=RelativePathCall.matcher)],
        )


@dataclass
class PathTextFinder(libcst.CSTVisitor):
    """
    Collects the places of a module that turn a path into text.
    """

    module: PositionedModule
    """
    The module visited.
    """

    paths: PathExpressions
    """
    What gives a path in the module.
    """

    found: list[PathText] = field(default_factory=list)
    """
    Each place, in the order of the source.
    """

    wrapped: set[libcst.Call] = field(default_factory=set)
    """
    The :func:`os.path.relpath` calls already turned back into a path.
    """

    @override
    def visit_Call(self, node: libcst.Call) -> None:
        """
        Collect a :class:`str` call on a path, or an unwrapped relative path.
        """
        if WrappedRelativePath.matches(node):
            self.wrapped.add(libcst.ensure_type(node.args[0].value, libcst.Call))
        if RelativePathCall.matches(node) and node not in self.wrapped:
            self.collect(node, node, PathTextShape.RELATIVE_PATH)
            return
        if (
            get_full_name_for_node(node.func) == str.__name__
            and len(node.args) == 1
            and node.args[0].keyword is None
            and not node.args[0].star
            and self.paths.gives_path(node.args[0].value)
        ):
            self.collect(node, node.args[0].value, PathTextShape.STRING_CONVERSION)

    @override
    def visit_FormattedStringExpression(
        self, node: libcst.FormattedStringExpression
    ) -> None:
        """
        Collect an f-string field interpolating a path as it is.
        """
        if (
            node.conversion is None
            and node.format_spec is None
            and node.equal is None
            and self.paths.gives_path(node.expression)
        ):
            self.collect(node, node.expression, PathTextShape.FORMATTED_FIELD)

    def collect(
        self,
        node: libcst.CSTNode,
        path: libcst.BaseExpression,
        shape: PathTextShape,
    ) -> None:
        """
        Keep the place *node* turning *path* into text as *shape* says.
        """
        self.found.append(PathText(self.module.positions[node], node, path, shape))


# %% the fix


class AsPosixFix(CodeFix[PathText]):
    """
    Turns the path into text with :meth:`pathlib.PurePath.as_posix`.
    """

    @classproperty
    def behaviour(cls) -> BehaviourDeclaration:
        return BehaviourDeclaration(
            BehaviourEffect.CHANGED,
            "The text separates the parts of a Windows path with / instead of \\; "
            "nothing changes on POSIX.",
        )

    def required_imports(self, specification: PathText) -> tuple[type, ...]:
        if specification.shape is PathTextShape.RELATIVE_PATH:
            return (Path,)
        return ()

    def replacement(self, specification: PathText) -> libcst.CSTNode:
        path = specification.path
        if specification.shape is PathTextShape.RELATIVE_PATH:
            path = libcst.Call(libcst.Name(Path.__name__), [libcst.Arg(path)])
        elif isinstance(path, libcst.BinaryOperation) and not path.lpar:
            path = path.with_changes(
                lpar=[libcst.LeftParen()], rpar=[libcst.RightParen()]
            )
        text = libcst.Call(
            libcst.Attribute(path, libcst.Name(PurePath.as_posix.__name__))
        )
        if specification.shape is PathTextShape.FORMATTED_FIELD:
            return specification.node.with_changes(expression=text)
        return text


# %% the check


@dataclass(frozen=True)
class PosixPathTextChecker(FixableChecker[PathText]):
    """
    Finds paths turned into text other than by :meth:`pathlib.PurePath.as_posix`,
    where the path is one the module's own code shows is a path.
    """

    enumerations: PathEnumerationFinder = field(
        default_factory=PathEnumerationFinder, compare=False
    )
    """
    Finds the path enumeration classes each module binds.
    """

    @classproperty
    def fix(cls) -> CodeFix[PathText]:
        return AsPosixFix()

    @classproperty
    def violation_description(cls) -> str:
        return (
            "turns a path into text that separates its parts with \\ on Windows; "
            f"call {PurePath.as_posix.__name__}() on the path"
        )

    @override
    def specifications_of_module(self, module: PositionedModule) -> Iterator[PathText]:
        finder = PathTextFinder(
            module, PathExpressions(self.enumerations.names_in(module.module))
        )
        module.module.visit(finder)
        yield from finder.found

"""
Renaming, in a file's base version, only the occurrences of a renamed definition's old
name that are proven to refer to that definition.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass, field
from functools import cached_property

from basstler.git.commit_range import FileVersions
from basstler.review_triage.commit_tree import PACKAGE_INITIALIZER
from basstler.review_triage.name_scopes import (
    COMPREHENSION_TYPES,
    NameScope,
    UnknownValue,
)
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.referents import (
    PROPERTY_ACCESSORS,
    RECEIVING_DECORATORS,
    SUPER,
    ClassInstance,
    MemberResolver,
    ModuleNames,
    Referent,
)
from basstler.review_triage.renames import (
    BindingRename,
    ClassAttribute,
    ModuleMember,
)

DEFINITION_KEYWORDS = re.compile(r"(?:async\s+)?(?:def|class)\s+")
"""
Matches the keywords of a function or class definition up to its name.
"""

# %% positions in a file's text


@dataclass(frozen=True)
class TextEdit:
    """
    A run of a file's text replaced by another.
    """

    start: int
    """
    The offset of the first character replaced.
    """

    end: int
    """
    The offset after the last character replaced.
    """

    replacement: str
    """
    What replaces the run.
    """


@dataclass(frozen=True)
class SourcePositions:
    """
    Converts the line and column positions of a file's syntax tree and tokens into
    offsets in its text.
    """

    text: str
    """
    The file's content.
    """

    @cached_property
    def lines(self) -> tuple[str, ...]:
        """
        The file's lines with their line ends, split where Python splits them.
        """
        return tuple(io.StringIO(self.text, newline="").readlines())

    @cached_property
    def line_starts(self) -> tuple[int, ...]:
        """
        The offset of each line's first character.
        """
        starts = [0]
        for line in self.lines:
            starts.append(starts[-1] + len(line))
        return tuple(starts)

    def node_offset(self, line: int, byte_column: int) -> int:
        """
        :param line: A line, counted from one, as a syntax tree gives it.
        :param byte_column: A column in UTF-8 bytes, as a syntax tree gives it.
        :return: The offset of that position.
        """
        prefix = self.lines[line - 1].encode()[:byte_column].decode()
        return self.line_starts[line - 1] + len(prefix)

    def token_offset(self, position: tuple[int, int]) -> int:
        """
        :param position: A line and character column, as :mod:`tokenize` gives them.
        :return: The offset of that position.
        """
        line, column = position
        return self.line_starts[line - 1] + column

    def definition_name_offset(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> int:
        """
        :param node: A function or class definition.
        :return: The offset of the name it defines, or of its keyword when no name
            follows it on its line.
        """
        start = self.node_offset(node.lineno, node.col_offset)
        line_start = self.line_starts[node.lineno - 1]
        keywords = DEFINITION_KEYWORDS.match(
            self.lines[node.lineno - 1], start - line_start
        )
        return start if keywords is None else line_start + keywords.end()


# %% finding the occurrences of one file


@dataclass(frozen=True)
class MethodReceiver:
    """
    The parameter a method of a module's top-level class receives its instance or its
    class by.
    """

    parameter_name: str
    """
    The parameter's name.
    """

    owner: ModuleMember
    """
    The class defining the method.
    """


@dataclass
class OccurrenceSearch(ast.NodeVisitor):
    """
    Finds the occurrences of renamed definitions' old names in one file that are proven
    to refer to those definitions, following the file's scopes, its classes and the
    receivers of their methods.
    """

    resolver: MemberResolver
    """
    What the commit's names refer to.
    """

    names: ModuleNames
    """
    The file searched.
    """

    renames: dict[str, tuple[BindingRename, ...]]
    """
    The renames searched for, by the definition's old name.
    """

    positions: SourcePositions
    """
    The file's positions.
    """

    scopes: list[NameScope] = field(default_factory=list)
    """
    The scopes enclosing the node visited, outermost first.
    """

    class_bodies: dict[int, ModuleMember] = field(default_factory=dict)
    """
    The class of each class body among :attr:`scopes`, by the scope's identity, for
    the module's top-level classes.
    """

    receivers: dict[int, MethodReceiver] = field(default_factory=dict)
    """
    The receiver of each method among :attr:`scopes`, by the scope's identity, for the
    methods of :attr:`class_bodies`.
    """

    edits: list[TextEdit] = field(default_factory=list)
    """
    The occurrences found, each with its new name.
    """

    def search(self) -> list[TextEdit]:
        """
        :return: The occurrences proven to refer to a renamed definition, each with its
            new name.
        """
        self.scopes = [self.names.scope]
        for statement in self.names.source.tree.body:
            self.visit(statement)
        return self.edits

    # %%% scopes

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """
        Visit the function's decorators, defaults and annotations in the enclosing
        scope, and its body in its own.

        :param node: The function.
        """
        outer = [*node.decorator_list, node.args]
        if node.returns is not None:
            outer.append(node.returns)
        body = NameScope.opened_by(node)
        receiver = self.method_receiver(node)
        if receiver is not None:
            self.receivers[id(body)] = receiver
        self.visit_definition(node, outer, body)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """
        Visit the class's decorators and bases in the enclosing scope, and its body in
        its own.

        :param node: The class.
        """
        body = NameScope.opened_by(node)
        owner = ModuleMember(self.names.module, node.name)
        if len(self.scopes) == 1 and self.resolver.class_definition(owner) is not None:
            self.class_bodies[id(body)] = owner
        self.visit_definition(
            node, [*node.decorator_list, *node.bases, *node.keywords], body
        )

    def visit_definition(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        outer: list[ast.AST],
        body: NameScope,
    ) -> None:
        """
        :param node: A function or class.
        :param outer: Its parts evaluated outside its body.
        :param body: The scope of its body.
        """
        self.found(node.name, self.positions.definition_name_offset(node))
        type_parameters = NameScope(
            {parameter.name: (UnknownValue(),) for parameter in node.type_params}
        )
        self.scopes.append(type_parameters)
        for part in outer:
            self.visit(part)
        self.scopes.append(body)
        for statement in node.body:
            self.visit(statement)
        del self.scopes[-2:]
        self.class_bodies.pop(id(body), None)
        self.receivers.pop(id(body), None)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        """
        Visit the lambda's defaults in the enclosing scope, and its body in its own.

        :param node: The lambda.
        """
        self.visit(node.args)
        self.scopes.append(NameScope.opened_by(node))
        self.visit(node.body)
        self.scopes.pop()

    def generic_visit(self, node: ast.AST) -> None:
        """
        Visit a comprehension in its own scope, an asynchronous function as any
        function, any other node in the current scope.

        :param node: The node visited.
        """
        if isinstance(node, ast.AsyncFunctionDef):
            self.visit_FunctionDef(node)
            return
        if not isinstance(node, COMPREHENSION_TYPES):
            super().generic_visit(node)
            return
        self.scopes.append(NameScope.opened_by(node))
        super().generic_visit(node)
        self.scopes.pop()

    def method_receiver(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> MethodReceiver | None:
        """
        :param node: A function defined in the current scope.
        :return: Its receiver, when it is a method of a top-level class whose
            decorators all leave its first parameter the instance or the class.
        """
        owner = self.class_bodies.get(id(self.scopes[-1]))
        parameters = (*node.args.posonlyargs, *node.args.args)
        if owner is None or not parameters:
            return None
        for decorator in node.decorator_list:
            is_accessor = (
                isinstance(decorator, ast.Attribute)
                and decorator.attr in PROPERTY_ACCESSORS
            )
            if not is_accessor and (
                self.expression_referent(decorator) not in RECEIVING_DECORATORS
            ):
                return None
        return MethodReceiver(parameters[0].arg, owner)

    # %%% occurrences

    def visit_Name(self, node: ast.Name) -> None:
        """
        :param node: A name the code uses or binds.
        """
        self.found(node.id, self.positions.node_offset(node.lineno, node.col_offset))

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """
        :param node: An attribute, which refers to a renamed definition when it is read
            from that definition's module, its class, an instance of the class as a
            method receives it, or ``super()`` in a method of a subclass.
        """
        self.visit(node.value)
        if node.attr not in self.renames:
            return
        end = self.positions.node_offset(node.end_lineno, node.end_col_offset)
        self.record(node.attr, end - len(node.attr), self.attribute_referent(node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """
        :param node: An import of module members, each renamed member among them
            imported by its new name, and bound by it when bound by its own name.
        """
        module = self.names.source.imported_module(node)
        for alias in node.names:
            if alias.name not in self.renames:
                continue
            referent = self.resolver.member_referent(module, alias.name)
            self.record(
                alias.name,
                self.positions.node_offset(alias.lineno, alias.col_offset),
                referent,
            )
            if alias.asname == alias.name:
                end = self.positions.node_offset(alias.end_lineno, alias.end_col_offset)
                self.record(alias.asname, end - len(alias.asname), referent)

    def found(self, name: str, offset: int) -> None:
        """
        :param name: A name the code uses or binds in the current scope.
        :param offset: Where it is.
        """
        if name in self.renames:
            self.record(name, offset, self.name_referent(name))

    def record(self, name: str, offset: int, referent: Referent | None) -> None:
        """
        :param name: An old name of a renamed definition.
        :param offset: Where it occurs.
        :param referent: What the occurrence refers to.
        """
        rename = next(
            (rename for rename in self.renames[name] if rename.definition == referent),
            None,
        )
        if rename is not None and self.positions.text[offset:].startswith(name):
            self.edits.append(TextEdit(offset, offset + len(name), rename.new_name))

    # %%% referents

    def name_referent(self, name: str) -> Referent | None:
        """
        :param name: A name the current scope uses.
        :return: What it refers to, ``None`` when it is not proven.
        """
        for depth, scope in enumerate(reversed(self.scopes)):
            if (scope.class_body and depth > 0) or name not in scope.bindings:
                continue
            if scope is self.scopes[0]:
                break
            if id(scope) in self.class_bodies:
                return self.class_body_referent(self.class_bodies[id(scope)], name)
            bindings = scope.bindings[name]
            receiver = self.receivers.get(id(scope))
            if len(bindings) != 1:
                return None
            if receiver is not None and receiver.parameter_name == name:
                return ClassInstance(receiver.owner)
            return self.resolver.imported_referent(self.names, bindings[0])
        return self.resolver.top_level_referent(self.names, name)

    def class_body_referent(self, owner: ModuleMember, name: str) -> Referent | None:
        """
        :param owner: A top-level class of the file.
        :param name: A name its body binds.
        :return: The class's attribute, ``None`` when the module binds the name too,
            so that its body may read the module's before binding its own.
        """
        if self.names.scope.imports_everything or name in self.names.scope.bindings:
            return None
        return ClassAttribute(owner, name)

    def expression_referent(self, expression: ast.expr) -> Referent | None:
        """
        :param expression: A name or a chain of attributes, a call looked through.
        :return: What it refers to, ``None`` when it is not proven.
        """
        if isinstance(expression, ast.Call):
            return self.expression_referent(expression.func)
        if isinstance(expression, ast.Name):
            return self.name_referent(expression.id)
        if not isinstance(expression, ast.Attribute):
            return None
        return self.attribute_referent(expression)

    def attribute_referent(self, node: ast.Attribute) -> Referent | None:
        """
        :param node: An attribute.
        :return: What it refers to, ``None`` when it is not proven.
        """
        receiver = self.receivers.get(id(self.scopes[-1]))
        if receiver is not None and self.is_super_call(node.value):
            return self.resolver.inherited_attribute_owner(receiver.owner, node.attr)
        if isinstance(node.value, ast.Call):
            return None
        return self.resolver.attribute_referent(
            self.expression_referent(node.value), node.attr
        )

    def is_super_call(self, expression: ast.expr) -> bool:
        """
        :param expression: An expression of the current scope.
        :return: Whether it calls the builtin ``super`` without arguments.
        """
        return (
            isinstance(expression, ast.Call)
            and not expression.args
            and not expression.keywords
            and self.expression_referent(expression.func) == SUPER
        )


# %% renaming a file's base version


@dataclass(frozen=True)
class MemberRenamer:
    """
    Renames, in a file's base version, every occurrence of a renamed module or class
    member's old name proven to refer to that member, and nothing else.
    """

    renames: tuple[BindingRename, ...]
    """
    The module and class members the pull request renames.
    """

    resolver: MemberResolver
    """
    What the base commit's names refer to.
    """

    def renamed_base(self, change: FileVersions) -> str:
        """
        :param change: A Python file the pull request changes, present in the base
            commit.
        :return: Its base version with the proven occurrences renamed; the occurrences
            in docstrings and comments too when every occurrence in its code is proven.
        """
        text = change.base_text
        mentioned = [
            rename
            for rename in self.renames
            if re.search(rf"\b{re.escape(rename.old_name)}\b", text)
        ]
        if not mentioned:
            return text
        path = change.previous_path or change.path
        names = ModuleNames.from_text(
            self.resolver.modules.module_path(path),
            text,
            path.name == PACKAGE_INITIALIZER,
        )
        if not names.source.parses:
            return text
        tokens = tuple(tokenize.generate_tokens(io.StringIO(text).readline))
        used_names = {token.string for token in tokens if token.type == tokenize.NAME}
        renames: dict[str, tuple[BindingRename, ...]] = {}
        for rename in mentioned:
            if rename.new_name not in used_names:
                old = rename.old_name
                renames[old] = (*renames.get(old, ()), rename)
        if not renames:
            return text
        positions = SourcePositions(text)
        edits = OccurrenceSearch(self.resolver, names, renames, positions).search()
        edits += self.prose_edits(names.source, tokens, positions, edits)
        return self.edited(text, edits)

    @staticmethod
    def prose_edits(
        source: PythonSource,
        tokens: tuple[tokenize.TokenInfo, ...],
        positions: SourcePositions,
        code_edits: list[TextEdit],
    ) -> list[TextEdit]:
        """
        :param source: The file.
        :param tokens: Its tokens.
        :param positions: Its positions.
        :param code_edits: The occurrences in its code proven to refer to a renamed
            member.
        :return: The renames of the docstrings and comments, for each old name every
            occurrence of which in the code is proven to refer to one member.
        """
        renamed = {edit.start: edit for edit in code_edits}
        replacements: dict[str, str] = {}
        excluded: set[str] = set()
        for token in tokens:
            if token.type != tokenize.NAME:
                continue
            edit = renamed.get(positions.token_offset(token.start))
            if edit is None or replacements.get(token.string, edit.replacement) != (
                edit.replacement
            ):
                excluded.add(token.string)
            else:
                replacements[token.string] = edit.replacement
        replacements = {
            old: new for old, new in replacements.items() if old not in excluded
        }
        if not replacements:
            return []
        documentation = {
            positions.node_offset(node.value.lineno, node.value.col_offset)
            for node in ast.walk(source.tree)
            if isinstance(node, ast.stmt) and PythonSource.is_documentation(node)
        }
        pattern = re.compile(rf"\b(?:{'|'.join(map(re.escape, replacements))})\b")
        prose = (
            token
            for token in tokens
            if token.type == tokenize.COMMENT
            or (
                token.type == tokenize.STRING
                and positions.token_offset(token.start) in documentation
            )
        )
        return [
            TextEdit(
                positions.token_offset(token.start),
                positions.token_offset(token.end),
                pattern.sub(lambda match: replacements[match.group()], token.string),
            )
            for token in prose
            if pattern.search(token.string)
        ]

    @staticmethod
    def edited(text: str, edits: list[TextEdit]) -> str:
        """
        :param text: A file's content.
        :param edits: Runs of it to replace, none overlapping another.
        :return: The content with every run replaced.
        """
        for edit in sorted(edits, key=lambda edit: edit.start, reverse=True):
            text = text[: edit.start] + edit.replacement + text[edit.end :]
        return text

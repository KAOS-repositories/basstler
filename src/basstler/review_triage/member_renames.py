"""
Renaming, in a file's base version, only the occurrences of a renamed module member's
old name that are proven to refer to that member.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass, field
from functools import cached_property

from basstler.git.commit_range import FileVersions
from basstler.review_triage.commit_tree import PACKAGE_INITIALIZER, CommitModules
from basstler.review_triage.name_scopes import (
    COMPREHENSION_TYPES,
    AssignedValue,
    DeclaredType,
    ImportedMember,
    ImportedModule,
    LocalDefinition,
    NameBinding,
    NameScope,
    UnknownValue,
)
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import (
    DOTTED_NAME_SEPARATOR,
    MemberRename,
    ModuleMember,
)

# %% what a name refers to


@dataclass(frozen=True)
class ModuleObject:
    """
    A module, as a name or an attribute refers to it.
    """

    module: str
    """
    The module's dotted path.
    """


Referent = ModuleMember | ModuleObject
"""
What a name or an attribute is proven to refer to.
"""

OWN_MEMBER_BINDINGS = (LocalDefinition, AssignedValue, DeclaredType)
"""
The bindings that make a module's top-level name a member the module itself defines.
"""

DEFINITION_KEYWORDS = re.compile(r"(?:async\s+)?(?:def|class)\s+")
"""
Matches the keywords of a function or class definition up to its name.
"""

# %% a module's top-level names


@dataclass(frozen=True)
class ModuleNames:
    """
    One version of a module, read for the names it binds.
    """

    module: str
    """
    The module's dotted path.
    """

    source: PythonSource
    """
    Its source, its relative imports resolved against its package.
    """

    @classmethod
    def from_text(cls, module: str, text: str, is_package: bool) -> ModuleNames:
        """
        :param module: The module's dotted path.
        :param text: Its source.
        :param is_package: Whether it is a package initializer.
        :return: The module.
        """
        components = tuple(module.split(DOTTED_NAME_SEPARATOR)) if module else ()
        package = components if is_package else components[:-1]
        return cls(module, PythonSource(text, package))

    @cached_property
    def scope(self) -> NameScope:
        """
        The names its top level binds.
        """
        return NameScope.opened_by(self.source.tree)


# %% resolving names across the commit


@dataclass
class MemberResolver:
    """
    Proves what the top-level names of one commit's modules refer to, following imports
    from module to module, each module read once.
    """

    modules: CommitModules
    """
    The commit's modules.
    """

    read_modules: dict[str, ModuleNames | None] = field(default_factory=dict)
    """
    Each module read so far, ``None`` when no single parsable file is that module.
    """

    def names_of(self, module: str) -> ModuleNames | None:
        """
        :param module: A dotted module path.
        :return: The module, ``None`` when no single parsable file of the commit is it.
        """
        if module not in self.read_modules:
            keys = self.modules.module_files.get(module, ())
            names = None
            if len(keys) == 1:
                text = self.modules.texts_of(keys)[keys[0]]
                is_package = keys[0].endswith(PACKAGE_INITIALIZER)
                names = ModuleNames.from_text(module, text, is_package)
            if names is not None and not names.source.parses:
                names = None
            self.read_modules[module] = names
        return self.read_modules[module]

    def member_referent(
        self,
        module: str,
        member_name: str,
        followed: frozenset[ModuleMember] = frozenset(),
    ) -> Referent | None:
        """
        :param module: A dotted module path.
        :param member_name: A name the module may bind at its top level.
        :param followed: The members whose imports are being followed.
        :return: What the name refers to, ``None`` when it is not proven.
        """
        member = ModuleMember(module, member_name)
        names = self.names_of(module)
        if names is None or member in followed:
            return None
        return self.top_level_referent(names, member_name, followed | {member})

    def top_level_referent(
        self,
        names: ModuleNames,
        name: str,
        followed: frozenset[ModuleMember] = frozenset(),
    ) -> Referent | None:
        """
        :param names: A module.
        :param name: A name its top level may bind.
        :param followed: The members whose imports are being followed.
        :return: What the name refers to, ``None`` when it is not proven: bound more
            than once, possibly by a star import, or also a submodule's name.
        """
        scope = names.scope
        submodule = f"{names.module}{DOTTED_NAME_SEPARATOR}{name}"
        is_submodule = submodule in self.modules.module_files
        bindings = scope.bindings.get(name, ())
        if scope.imports_everything:
            return None
        if not bindings:
            return ModuleObject(submodule) if is_submodule else None
        if len(bindings) != 1 or is_submodule:
            return None
        if isinstance(bindings[0], OWN_MEMBER_BINDINGS):
            return ModuleMember(names.module, name)
        return self.imported_referent(names, bindings[0], followed)

    def imported_referent(
        self,
        names: ModuleNames,
        binding: NameBinding,
        followed: frozenset[ModuleMember] = frozenset(),
    ) -> Referent | None:
        """
        :param names: The module holding the binding.
        :param binding: How one of its scopes binds a name.
        :param followed: The members whose imports are being followed.
        :return: What the import binds the name to, ``None`` for any other binding.
        """
        if isinstance(binding, ImportedModule):
            return ModuleObject(binding.module)
        if isinstance(binding, ImportedMember):
            return self.member_referent(
                names.source.imported_module(binding.statement),
                binding.defined_name,
                followed,
            )
        return None


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


@dataclass
class OccurrenceSearch(ast.NodeVisitor):
    """
    Finds the occurrences of renamed members' old names in one file that are proven to
    refer to those members, following the file's scopes.
    """

    resolver: MemberResolver
    """
    What the commit's names refer to.
    """

    names: ModuleNames
    """
    The file searched.
    """

    renames: dict[str, tuple[MemberRename, ...]]
    """
    The renames searched for, by the member's old name.
    """

    positions: SourcePositions
    """
    The file's positions.
    """

    scopes: list[NameScope] = field(default_factory=list)
    """
    The scopes enclosing the node visited, outermost first.
    """

    edits: list[TextEdit] = field(default_factory=list)
    """
    The occurrences found, each with its new name.
    """

    def search(self) -> list[TextEdit]:
        """
        :return: The occurrences proven to refer to a renamed member, each with its new
            name.
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
        self.visit_definition(node, outer)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """
        Visit the class's decorators and bases in the enclosing scope, and its body in
        its own.

        :param node: The class.
        """
        self.visit_definition(node, [*node.decorator_list, *node.bases, *node.keywords])

    def visit_definition(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        outer: list[ast.AST],
    ) -> None:
        """
        :param node: A function or class.
        :param outer: Its parts evaluated outside its body.
        """
        self.found(node.name, self.positions.definition_name_offset(node))
        type_parameters = NameScope(
            {parameter.name: (UnknownValue(),) for parameter in node.type_params}
        )
        self.scopes.append(type_parameters)
        for part in outer:
            self.visit(part)
        self.scopes.append(NameScope.opened_by(node))
        for statement in node.body:
            self.visit(statement)
        del self.scopes[-2:]

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

    # %%% occurrences

    def visit_Name(self, node: ast.Name) -> None:
        """
        :param node: A name the code uses or binds.
        """
        self.found(node.id, self.positions.node_offset(node.lineno, node.col_offset))

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """
        :param node: An attribute, which refers to a renamed member when it is read
            from that member's module.
        """
        self.visit(node.value)
        if node.attr not in self.renames:
            return
        module = self.expression_referent(node.value)
        if not isinstance(module, ModuleObject):
            return
        end = self.positions.node_offset(node.end_lineno, node.end_col_offset)
        self.record(
            node.attr,
            end - len(node.attr),
            self.resolver.member_referent(module.module, node.attr),
        )

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
        :param name: An old name of a renamed member.
        :param offset: Where it occurs.
        :param referent: What the occurrence refers to.
        """
        rename = next(
            (rename for rename in self.renames[name] if rename.member == referent),
            None,
        )
        if rename is not None and self.positions.text[offset:].startswith(name):
            self.edits.append(
                TextEdit(offset, offset + len(name), rename.new_member_name)
            )

    def name_referent(self, name: str) -> Referent | None:
        """
        :param name: A name the current scope uses.
        :return: What it refers to, ``None`` when it is not proven.
        """
        for depth, scope in enumerate(reversed(self.scopes)):
            if (scope.class_body and depth > 0) or name not in scope.bindings:
                continue
            if scope is self.scopes[0]:
                return self.resolver.top_level_referent(self.names, name)
            bindings = scope.bindings[name]
            if len(bindings) != 1:
                return None
            return self.resolver.imported_referent(self.names, bindings[0])
        return None

    def expression_referent(self, expression: ast.expr) -> Referent | None:
        """
        :param expression: A name or a chain of attributes.
        :return: What it refers to, ``None`` when it is not proven.
        """
        if isinstance(expression, ast.Name):
            return self.name_referent(expression.id)
        if not isinstance(expression, ast.Attribute):
            return None
        module = self.expression_referent(expression.value)
        if not isinstance(module, ModuleObject):
            return None
        return self.resolver.member_referent(module.module, expression.attr)


# %% renaming a file's base version


@dataclass(frozen=True)
class MemberRenamer:
    """
    Renames, in a file's base version, every occurrence of a renamed member's old name
    proven to refer to that member, and nothing else.
    """

    renames: tuple[MemberRename, ...]
    """
    The members the pull request renames.
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
            if re.search(rf"\b{re.escape(rename.member.member_name)}\b", text)
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
        renames: dict[str, tuple[MemberRename, ...]] = {}
        for rename in mentioned:
            if rename.new_member_name not in used_names:
                old = rename.member.member_name
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

"""
The parts of a Python file a change to it is judged by: its code, the names its imports
bind, its documentation strings and its comments.
"""

from __future__ import annotations

import ast
import io
import keyword
import tokenize
import warnings
from bisect import bisect_left
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from functools import cache, cached_property

from basstler.git.commit_range import FileVersions
from basstler.review_triage.name_scopes import STAR_IMPORT
from basstler.review_triage.renames import DOTTED_NAME_SEPARATOR, RenameMap

# %% names in the syntax tree


class IdentifierField(StrEnum):
    """
    The fields of a syntax tree node that hold an identifier, or a list of them,
    wherever the node type has such a field.
    """

    IDENTIFIER = "id"
    """
    The name a :class:`ast.Name` refers to.
    """

    ATTRIBUTE = "attr"
    """
    The attribute an :class:`ast.Attribute` reads.
    """

    NAME = "name"
    """
    The name a definition or a pattern binds, or the name an import alias imports.
    """

    ARGUMENT = "arg"
    """
    The name of a parameter or of a keyword argument.
    """

    ALIAS = "asname"
    """
    The name an import binds its module or member to.
    """

    MODULE = "module"
    """
    The module an ``import ...

    from`` reads.
    """

    NAMES = "names"
    """
    The names a ``global`` or ``nonlocal`` statement declares.
    """

    REST = "rest"
    """
    The name a mapping pattern binds the remaining keys to.
    """

    KEYWORD_ATTRIBUTES = "kwd_attrs"
    """
    The attributes a class pattern matches by keyword.
    """


OPTIONAL = "Optional"
"""
The typing name of a value that may also be ``None``.
"""

FUTURE_MODULE = "__future__"
"""
The module whose imports change how the rest of the file is compiled.
"""

SECTION_HEADER = "# %%"
"""
What a comment opening a section of a file starts with.
"""

METADATA_ANNOTATION = "Annotated"
"""
The typing name of a type followed by metadata that does not change it.
"""

LITERAL = "Literal"
"""
The typing name of a type allowing only the values it lists.
"""

TUPLE_CLASSES = frozenset({"tuple", "Tuple"})
"""
The names of the tuple class, whose annotation ``tuple[X, ...]`` declares any number of
``X``.
"""

# %% type annotations


class ContainerKind(Enum):
    """
    How a standard container gives the values it holds.
    """

    SEQUENCE = auto()
    """
    Iterating, indexing and removing an item give its one type argument.
    """

    MAPPING = auto()
    """
    Iterating gives its first type argument, the key; indexing, ``get``, ``pop`` and
    ``setdefault`` give its second, the value.
    """


CONTAINER_KINDS: dict[str, ContainerKind] = {
    **dict.fromkeys(
        (
            "list",
            "List",
            "set",
            "Set",
            "frozenset",
            "FrozenSet",
            "AbstractSet",
            "MutableSet",
            "Sequence",
            "MutableSequence",
            "Collection",
            "Iterable",
            "Iterator",
            "Generator",
            "Reversible",
            "deque",
            "Deque",
            "KeysView",
            "ValuesView",
            *TUPLE_CLASSES,
        ),
        ContainerKind.SEQUENCE,
    ),
    **dict.fromkeys(
        (
            "dict",
            "Dict",
            "Mapping",
            "MutableMapping",
            "defaultdict",
            "DefaultDict",
            "OrderedDict",
        ),
        ContainerKind.MAPPING,
    ),
}
"""
The standard containers, by the name of their class or typing alias.
"""
REMOVED_ITEM_METHODS: dict[ContainerKind, frozenset[str]] = {
    ContainerKind.SEQUENCE: frozenset({"pop", "popleft"}),
    ContainerKind.MAPPING: frozenset({"get", "pop", "setdefault"}),
}
"""
The methods of each kind of container returning one of the items indexing gives.
"""


@dataclass(frozen=True, slots=True)
class MappingView:
    """
    A view a method of a mapping returns.
    """

    view_class: str
    """
    The name of the view's class.
    """
    held_argument: int
    """
    The position of the mapping's type argument the view holds.
    """


MAPPING_VIEWS: dict[str, MappingView] = {
    "keys": MappingView("KeysView", 0),
    "values": MappingView("ValuesView", 1),
}
"""
The methods of a mapping returning a view, by name.
"""
COPY_METHOD = "copy"
"""
The method of a standard container returning a shallow copy of it.
"""


@dataclass(frozen=True, slots=True)
class AnnotatedType:
    """
    What a type annotation declares a value to be: an instance of one class, holding the
    values its type arguments declare.
    """

    class_name: str
    """
    The name of the class the value is an instance of.
    """

    arguments: tuple[AnnotatedType | None, ...] = ()
    """
    What the type arguments declare, ``None`` for one allowing no single class; a tuple
    of any length has its one item type only.
    """

    @classmethod
    def from_annotation(
        cls, annotation: ast.expr, type_variables: frozenset[str] = frozenset()
    ) -> AnnotatedType | None:
        """
        :param annotation: A type annotation.
        :param type_variables: The type variables in scope, which allow no single
            class.
        :return: What it declares, ``None`` aside, ``None`` when it allows no single
            class.
        """
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            sides = [
                side
                for side in (annotation.left, annotation.right)
                if not (isinstance(side, ast.Constant) and side.value is None)
            ]
            if len(sides) != 1:
                return None
            return cls.from_annotation(sides[0], type_variables)
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            reference = PythonSource.from_text(annotation.value)
            if not (
                reference.parses
                and len(reference.tree.body) == 1
                and isinstance(reference.tree.body[0], ast.Expr)
            ):
                return None
            return cls.from_annotation(reference.tree.body[0].value, type_variables)
        if isinstance(annotation, (ast.Name, ast.Attribute)):
            name = PythonSource.referenced_name(annotation)
            return None if name is None or name in type_variables else cls(name)
        if not isinstance(annotation, ast.Subscript):
            return None
        name = PythonSource.referenced_name(annotation.value)
        elements = annotation.slice
        arguments = elements.elts if isinstance(elements, ast.Tuple) else [elements]
        if name in (OPTIONAL, METADATA_ANNOTATION):
            return cls.from_annotation(arguments[0], type_variables)
        if name is None or name in type_variables or name == LITERAL:
            return None
        if (
            name in TUPLE_CLASSES
            and len(arguments) == 2
            and isinstance(arguments[1], ast.Constant)
            and arguments[1].value is Ellipsis
        ):
            arguments = arguments[:1]
        return cls(
            name,
            tuple(
                cls.from_annotation(argument, type_variables) for argument in arguments
            ),
        )

    @property
    def plain_class(self) -> str | None:
        """
        The class name when the annotation gives it no type arguments, ``None``
        otherwise.
        """
        return None if self.arguments else self.class_name

    @property
    def container_kind(self) -> ContainerKind | None:
        """
        How the value gives what it holds, ``None`` when it is no standard container or
        the annotation does not declare what it holds.
        """
        kind = CONTAINER_KINDS.get(self.class_name)
        if kind is ContainerKind.MAPPING and len(self.arguments) != 2:
            return None
        if kind is ContainerKind.SEQUENCE and len(self.arguments) != 1:
            return None
        return kind

    @property
    def element(self) -> AnnotatedType | None:
        """
        What iterating over the value gives, ``None`` when not declared.
        """
        if self.container_kind is None:
            return None
        return self.arguments[0]

    @property
    def item(self) -> AnnotatedType | None:
        """
        What indexing the value with one key gives, ``None`` when not declared.
        """
        if self.container_kind is None:
            return None
        return self.arguments[-1]

    def method_result(self, method: str) -> AnnotatedType | None:
        """
        :param method: The name of a method of the value.
        :return: What calling it returns, ``None`` when it is no method of a standard
            container returning a declared value.
        """
        kind = self.container_kind
        if kind is None:
            return None
        if method == COPY_METHOD:
            return self
        if method in REMOVED_ITEM_METHODS[kind]:
            return self.item
        if kind is ContainerKind.MAPPING and method in MAPPING_VIEWS:
            view = MAPPING_VIEWS[method]
            return AnnotatedType(view.view_class, (self.arguments[view.held_argument],))
        return None

    def in_base(self, renames: RenameMap) -> AnnotatedType:
        """
        :param renames: The renames from the names it is spelled with to the base
            commit's.
        :return: It with every class named as the base commit names it.
        """
        return AnnotatedType(
            renames.original_identifier(self.class_name),
            tuple(
                None if argument is None else argument.in_base(renames)
                for argument in self.arguments
            ),
        )


@dataclass(frozen=True)
class IdentifierRenamer(ast.NodeVisitor):
    """
    Replaces, in place, every identifier of a syntax tree that a rename map renames.
    """

    renames: RenameMap
    """
    The renames to apply.
    """

    @cached_property
    def identifier_field_names(self) -> frozenset[str]:
        """
        The name of every :class:`IdentifierField`.
        """
        return frozenset(IdentifierField)

    def generic_visit(self, node: ast.AST) -> None:
        """
        Rename the identifiers *node* holds, then visit its children.

        :param node: The node visited.
        """
        for field_name, value in ast.iter_fields(node):
            if field_name not in self.identifier_field_names:
                continue
            if isinstance(value, str):
                setattr(node, field_name, self.renames.renamed_identifier(value))
            elif isinstance(value, list) and all(
                isinstance(item, str) for item in value
            ):
                setattr(
                    node,
                    field_name,
                    [self.renames.renamed_identifier(item) for item in value],
                )
        super().generic_visit(node)


# %% one import binding


@dataclass(frozen=True)
class ImportBinding:
    """
    A name an import statement binds, and what it binds it to.
    """

    bound_name: str
    """
    The name the rest of the file refers to.
    """

    source: str
    """
    The dotted path of the module or module member the name is bound to.
    """

    @property
    def member_name(self) -> str:
        """
        The last name of :attr:`source`, the member's name in its module.
        """
        return self.source.rpartition(DOTTED_NAME_SEPARATOR)[2]


@dataclass(frozen=True)
class ImportBindings:
    """
    Every name a file's import statements bind.
    """

    bindings: frozenset[ImportBinding]
    """
    The bindings, wherever in the file their import statement is.
    """

    def sources_of(self, bound_name: str) -> frozenset[str]:
        """
        :param bound_name: A name the imports may bind.
        :return: Everything the imports bind it to.
        """
        return frozenset(
            binding.source
            for binding in self.bindings
            if binding.bound_name == bound_name
        )

    def refers_to(self, expression: ast.expr, module: str, member: str) -> bool:
        """
        :param expression: A name or an attribute in the file.
        :param module: The module defining the member.
        :param member: The member's name in it.
        :return: Whether the expression refers to that member through these bindings.
        """
        if isinstance(expression, ast.Name):
            return self.sources_of(expression.id) == {f"{module}.{member}"}
        return (
            isinstance(expression, ast.Attribute)
            and expression.attr == member
            and isinstance(expression.value, ast.Name)
            and self.sources_of(expression.value.id) == {module}
        )

    @property
    def bound_names(self) -> frozenset[str]:
        """
        Every name the imports bind, ``*`` for a star import.
        """
        return frozenset(binding.bound_name for binding in self.bindings)

    def unexplained_bindings(
        self, other: ImportBindings, referenced_names: frozenset[str]
    ) -> tuple[ImportBinding, ...]:
        """
        :param other: The bindings of another version of the file.
        :param referenced_names: The names this version's code refers to.
        :return: The star imports the other version lacks, and each name only these
            bindings bind that the code does not refer to or that both versions did
            not reach through the same star import of its module, by name.
        """
        star_sources = self.sources_of(STAR_IMPORT)
        other_star_sources = other.sources_of(STAR_IMPORT)
        if star_sources != other_star_sources:
            unexplained = {
                binding
                for binding in self.bindings
                if binding.bound_name == STAR_IMPORT
                and binding.source not in other_star_sources
            }
        else:
            unexplained = {
                binding
                for binding in self.bindings
                if binding.bound_name not in other.bound_names
                and not (
                    binding.bound_name in referenced_names
                    and binding.source.rpartition(DOTTED_NAME_SEPARATOR)[0]
                    + DOTTED_NAME_SEPARATOR
                    + STAR_IMPORT
                    in star_sources
                )
            }
        return tuple(
            sorted(
                unexplained, key=lambda binding: (binding.bound_name, binding.source)
            )
        )

    def disagreeing_names(
        self, other: ImportBindings, equivalence: ImportSourceEquivalence
    ) -> tuple[str, ...]:
        """
        :param other: The bindings of another version of the file.
        :param equivalence: Decides whether two sources bind one object.
        :return: Each name both bind, in order, that they bind to different sources
            but for one source each that *equivalence* proves binds the same object.
        """
        return tuple(
            bound_name
            for bound_name in sorted(self.bound_names & other.bound_names)
            if not self.binds_alike(bound_name, other, equivalence)
        )

    def binds_alike(
        self,
        bound_name: str,
        other: ImportBindings,
        equivalence: ImportSourceEquivalence,
    ) -> bool:
        """
        :param bound_name: A name both bindings bind.
        :param other: The bindings of another version of the file.
        :param equivalence: Decides whether two sources bind one object.
        :return: Whether both bind it to the same sources, or each to one source
            *equivalence* proves binds the other's object.
        """
        sources = self.sources_of(bound_name)
        other_sources = other.sources_of(bound_name)
        if sources == other_sources:
            return True
        if len(sources) != 1 or len(other_sources) != 1:
            return False
        (source,) = sources
        (other_source,) = other_sources
        return equivalence.binds_one_object(source, other_source)


class ImportSourceEquivalence:
    """
    Decides whether two import sources bind one object, proving it only for equal
    sources.
    """

    def binds_one_object(self, source: str, other_source: str) -> bool:
        """
        :param source: The dotted path one version of a file imports a name from.
        :param other_source: The dotted path another version imports it from.
        :return: Whether both are proven to bind one object.
        """
        return source == other_source


@dataclass(frozen=True)
class OwnerImports:
    """
    The imports a file's version renamed for moves gains and may lose: the new owner of
    each moved attribute or definition it reads, and an old owner it reads nothing else
    of.
    """

    added: frozenset[ImportBinding] = frozenset()
    """
    The bindings reading the moved attributes and definitions from where they moved.
    """

    droppable: frozenset[ImportBinding] = frozenset()
    """
    The bindings reading from where the moved attributes and definitions left, that
    nothing else reads in the file or from it.
    """

    def applied_to(
        self, bindings: ImportBindings, other: ImportBindings
    ) -> ImportBindings:
        """
        :param bindings: The bindings of the renamed version.
        :param other: The bindings of the version it is compared with.
        :return: *bindings* with each added binding *other* binds too, and without each
            droppable one *other* does not bind.
        """
        kept = {
            binding
            for binding in bindings.bindings
            if binding not in self.droppable or binding in other.bindings
        }
        return ImportBindings(frozenset(kept | (self.added & other.bindings)))

    def __or__(self, other: OwnerImports) -> OwnerImports:
        """
        :param other: Other imports gained and lost.
        :return: Those of both.
        """
        return OwnerImports(self.added | other.added, self.droppable | other.droppable)


# %% a run of lines


@dataclass(frozen=True)
class LineSpan:
    """
    Consecutive lines of a file, counted from one, both ends included.
    """

    first: int
    """
    The first line.
    """

    last: int
    """
    The last line.
    """


@dataclass(frozen=True)
class BlockStep:
    """
    One step from a block of statements into a block a statement of it holds.
    """

    statement: int
    """
    The position of that statement among the block's code statements.
    """

    field_name: str
    """
    The field of the statement holding the inner block, such as ``body``.
    """


@dataclass(frozen=True)
class DocumentationPlace:
    """
    Where a documentation string stands, by the code statements around it, so that the
    places of two versions whose code matches agree.
    """

    block: tuple[BlockStep, ...]
    """
    The steps from the module's body to the block holding the string.
    """

    preceding_statements: int
    """
    How many of the block's code statements come before the string.
    """

    ordinal: int
    """
    The string's position among the documentation strings right after them.
    """


# %% the file's parts


@dataclass(frozen=True)
class PythonSource:
    """
    One version of a Python file, split into the parts a change to it is judged by.
    """

    text: str
    """
    The file's content.
    """

    package: tuple[str, ...] = ()
    """
    The names of the directories holding the file, from the repository's root; empty
    when unknown, which leaves relative imports unresolved.
    """

    code_trees: dict[RenameMap, ast.Module] = field(
        default_factory=dict, compare=False, repr=False
    )
    """
    :meth:`code_tree` under each renames asked for so far.
    """

    @classmethod
    @cache
    def from_text(cls, text: str, package: tuple[str, ...] = ()) -> PythonSource:
        """
        :param text: The file's content.
        :param package: As :attr:`package`.
        :return: The one source of that text in that package for the whole process,
            so each part of it is read once however often it is asked for.
        """
        return cls(text, package)

    @cached_property
    def tree(self) -> ast.Module:
        """
        The file's syntax tree.

        :raises SyntaxError: If the file is not valid Python.
        """
        return self.parse()

    def parse(self) -> ast.Module:
        """
        :return: A new syntax tree of the file, without the warnings Python gives about
            the code it parses.
        :raises SyntaxError: If the file is not valid Python.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            return ast.parse(self.text)

    @staticmethod
    def every_version_parses(change: FileVersions) -> bool:
        """
        :param change: A changed file.
        :return: Whether each version of it that exists is valid Python.
        """
        return all(
            PythonSource.from_text(text).parses
            for text in (change.base_text, change.head_text)
            if text is not None
        )

    @cached_property
    def parses(self) -> bool:
        """
        Whether the text is valid Python.
        """
        try:
            return isinstance(self.tree, ast.Module)
        except SyntaxError:
            return False

    def renamed_tree(self, renames: RenameMap) -> ast.Module:
        """
        :param renames: The renames to apply.
        :return: A new syntax tree of the file with every identifier the renames
            rename replaced.
        :raises SyntaxError: If the file is not valid Python.
        """
        tree = self.parse()
        if renames.renames:
            IdentifierRenamer(renames).visit(tree)
        return tree

    def code_tree(self, renames: RenameMap) -> ast.Module:
        """
        :param renames: The renames to apply first.
        :return: The file's syntax tree without its imports and with every
            documentation string emptied; not to be modified, as it is kept for the
            next call.
        """
        if renames in self.code_trees:
            return self.code_trees[renames]
        tree = self.renamed_tree(renames)
        for node in list(ast.walk(tree)):
            for field_name, value in ast.iter_fields(node):
                if isinstance(value, list) and all(
                    isinstance(item, ast.stmt) for item in value
                ):
                    setattr(node, field_name, list(self.code_statements(value)))
        self.code_trees[renames] = tree
        return tree

    def code(self, renames: RenameMap) -> str:
        """
        :param renames: The renames to apply first.
        :return: :meth:`code_tree`, dumped as text.
        """
        return ast.dump(self.code_tree(renames))

    @staticmethod
    def code_statements(statements: list[ast.stmt]) -> Iterator[ast.stmt]:
        """
        :param statements: A block of statements.
        :return: Its statements other than imports, each documentation string emptied in its place.
        """
        for statement in statements:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                continue
            if PythonSource.is_documentation(statement):
                emptied = ast.copy_location(ast.Constant(""), statement.value)
                yield ast.copy_location(ast.Expr(emptied), statement)
                continue
            yield statement

    @staticmethod
    def is_documentation(statement: ast.stmt) -> bool:
        """
        :param statement: A statement.
        :return: Whether it is a bare string, which documents what precedes or holds it.
        """
        return (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )

    def imports(self, renames: RenameMap) -> ImportBindings:
        """
        :param renames: The renames to apply first.
        :return: The names the file's imports bind, other than those of ``__future__``.
        """
        renamed = renames.renamed_identifier
        bindings: set[ImportBinding] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                bindings |= {
                    ImportBinding(
                        renamed(alias.asname or alias.name.split(".")[0]),
                        renamed(alias.name),
                    )
                    for alias in node.names
                }
            elif isinstance(node, ast.ImportFrom) and node.module != FUTURE_MODULE:
                module = self.imported_module(node)
                bindings |= {
                    ImportBinding(
                        renamed(alias.asname or alias.name),
                        renamed(f"{module}.{alias.name}"),
                    )
                    for alias in node.names
                }
        return ImportBindings(frozenset(bindings))

    def imported_module(self, node: ast.ImportFrom) -> str:
        """
        :param node: A ``from`` import of the file.
        :return: The dotted path of the module it imports from, resolved against
            :attr:`package` when it is relative and reaches no higher than its root.
        """
        relative = "." * node.level + (node.module or "")
        parents = node.level - 1
        if node.level == 0 or not self.package or parents > len(self.package):
            return relative
        components = list(self.package[: len(self.package) - parents])
        if node.module:
            components.append(node.module)
        return ".".join(components)

    @cached_property
    def defined_names(self) -> frozenset[str]:
        """
        The names the file's top-level functions, classes and assignments define.
        """
        return frozenset().union(
            *(self.names_defined_by(statement) for statement in self.tree.body)
        )

    @staticmethod
    def names_defined_by(statement: ast.stmt) -> frozenset[str]:
        """
        :param statement: A statement.
        :return: The names it defines as a function, a class or an assignment.
        """
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            return frozenset({statement.name})
        if not isinstance(statement, ast.Assign | ast.AnnAssign | ast.AugAssign):
            return frozenset()
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        return frozenset(
            node.id
            for target in targets
            for node in ast.walk(target)
            if isinstance(node, ast.Name)
        )

    def referenced_names(self, renames: RenameMap) -> frozenset[str]:
        """
        :param renames: The renames to apply first.
        :return: The bare names the file's code, imports aside, refers to.
        """
        return frozenset(
            node.id
            for node in ast.walk(self.code_tree(renames))
            if isinstance(node, ast.Name)
        )

    @cached_property
    def decorator_only_names(self) -> frozenset[str]:
        """
        The bare names the file's code refers to only as whole decorators.
        """
        tree = self.code_tree(RenameMap())
        decorators = {
            id(decorator)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Name)
        }
        names = [node for node in ast.walk(tree) if isinstance(node, ast.Name)]
        elsewhere = {node.id for node in names if id(node) not in decorators}
        return frozenset(node.id for node in names) - elsewhere

    @cached_property
    def import_bindings(self) -> ImportBindings:
        """
        The names the file's imports bind, as the file spells them.
        """
        return self.imports(RenameMap())

    @cached_property
    def import_statements(self) -> str:
        """
        The file's import statements, those of ``__future__`` included, dumped as text
        in the order they occur.
        """
        return "\n".join(
            ast.dump(node)
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        )

    @cached_property
    def documentation(self) -> tuple[str, ...]:
        """
        The file's documentation strings, in the order they occur.
        """
        return tuple(
            statement.value.value for statement in self.documentation_statements
        )

    @cached_property
    def documentation_statements(self) -> tuple[ast.Expr, ...]:
        """
        The statements holding the file's documentation strings, in the order they
        occur.
        """
        return tuple(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.stmt) and self.is_documentation(node)
        )

    @cached_property
    def module_documentation(self) -> str | None:
        """
        The documentation string at the top of the file, ``None`` when it has none.
        """
        return ast.get_docstring(self.tree, clean=False)

    @cached_property
    def without_module_documentation(self) -> PythonSource:
        """
        The file without the documentation string at the top, itself when it has none or
        shares its lines with other code.
        """
        first = next(iter(self.tree.body), None)
        if first is None or not self.is_documentation(first):
            return self
        span = LineSpan(first.lineno, first.end_lineno)
        shares_lines = any(
            statement.lineno <= span.last for statement in self.tree.body[1:2]
        )
        if shares_lines:
            return self
        return self.without((span,))

    @cached_property
    def placed_documentation(self) -> dict[DocumentationPlace, ast.stmt]:
        """
        The statements holding the documentation strings of the file's functions,
        classes and fields, by where they stand; the module's own is left out.
        """
        placed = dict(self.documentation_in_block((), self.tree.body))
        first = next(iter(self.tree.body), None)
        return {
            place: statement
            for place, statement in placed.items()
            if statement is not first
        }

    @classmethod
    def documentation_in_block(
        cls, block: tuple[BlockStep, ...], statements: list[ast.stmt]
    ) -> Iterator[tuple[DocumentationPlace, ast.stmt]]:
        """
        :param block: The steps from the module's body to *statements*.
        :param statements: A block of statements.
        :return: The documentation strings in it and in the blocks its statements hold,
            each with its place.
        """
        code_statements = 0
        ordinal = 0
        for statement in statements:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                continue
            if cls.is_documentation(statement):
                yield DocumentationPlace(block, code_statements, ordinal), statement
                ordinal += 1
                continue
            ordinal = 0
            for field_name, value in ast.iter_fields(statement):
                if (
                    isinstance(value, list)
                    and value
                    and all(isinstance(item, ast.stmt) for item in value)
                ):
                    yield from cls.documentation_in_block(
                        (*block, BlockStep(code_statements, field_name)), value
                    )
            code_statements += 1

    def without_documentation_missing_from(self, other: PythonSource) -> PythonSource:
        """
        :param other: The other version of the file.
        :return: The file without the documentation strings of functions, classes and
            fields that *other* has none in the place of, keeping those sharing lines
            with other code; itself when none is left out or the rest does not parse.
        """
        spans = tuple(
            LineSpan(statement.lineno, statement.end_lineno)
            for place, statement in self.placed_documentation.items()
            if place not in other.placed_documentation
            and self.stands_on_own_lines(statement)
        )
        if not spans:
            return self
        remaining = self.without(spans)
        return remaining if remaining.parses else self

    def stands_on_own_lines(self, statement: ast.stmt) -> bool:
        """
        :param statement: A statement of the file.
        :return: Whether no other code shares its first or last line.
        """
        lines = self.text.splitlines()
        before = lines[statement.lineno - 1].encode()[: statement.col_offset]
        after = lines[statement.end_lineno - 1].encode()[statement.end_col_offset :]
        return not before.strip() and (
            not after.strip() or after.strip().startswith(b"#")
        )

    @cached_property
    def comments(self) -> str:
        """
        The text of the file's comments, one per line, in the order they occur.
        """
        return "\n".join(
            token.string.removeprefix("#") for token in self.comment_tokens
        )

    @cached_property
    def comment_tokens(self) -> tuple[tokenize.TokenInfo, ...]:
        """
        The file's comments, in the order they occur.
        """
        return tuple(
            token
            for token in tokenize.generate_tokens(io.StringIO(self.text).readline)
            if token.type == tokenize.COMMENT
        )

    def first_comment_line_differing_from(self, other: PythonSource) -> int:
        """
        :param other: Another version of the file.
        :return: The line of the first of this version's comments that reads otherwise
            than the other's comment in its place, else of its last comment, else 1.
        """
        for token, other_token in zip(
            self.comment_tokens, other.comment_tokens, strict=False
        ):
            if token.string != other_token.string:
                return token.start[0]
        if len(self.comment_tokens) > len(other.comment_tokens):
            return self.comment_tokens[len(other.comment_tokens)].start[0]
        return self.comment_tokens[-1].start[0] if self.comment_tokens else 1

    def import_line(self, bound_name: str) -> int:
        """
        :param bound_name: A name an import of either version of the file binds.
        :return: The line of this version's import statement binding it, else of its
            first import statement, else 1.
        """
        statements = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        binding = next(
            (
                statement
                for statement in statements
                for alias in statement.names
                if bound_name == (alias.asname or alias.name.split(".")[0])
            ),
            None,
        )
        if binding is not None:
            return binding.lineno
        return min((statement.lineno for statement in statements), default=1)

    @cached_property
    def significant_tokens(self) -> tuple[tokenize.TokenInfo, ...]:
        """
        The file's tokens that carry meaning - names, operators, numbers and strings -
        in order.
        """
        return tuple(
            token
            for token in tokenize.generate_tokens(io.StringIO(self.text).readline)
            if token.type
            in (tokenize.NAME, tokenize.OP, tokenize.NUMBER, tokenize.STRING)
        )

    def tokens_on_lines(self, first: int, end: int) -> tuple[tokenize.TokenInfo, ...]:
        """
        :param first: The number of the first line, counted from one.
        :param end: The number of the line after the last.
        :return: The :attr:`significant_tokens` starting on those lines.
        """
        return self.significant_tokens[
            bisect_left(self.significant_token_lines, first) : bisect_left(
                self.significant_token_lines, end
            )
        ]

    @cached_property
    def significant_token_lines(self) -> tuple[int, ...]:
        """
        The line each of :attr:`significant_tokens` starts on, in the same order, which
        never decreases.
        """
        return tuple(token.start[0] for token in self.significant_tokens)

    @staticmethod
    def referenced_name(expression: ast.expr) -> str | None:
        """
        :param expression: An expression naming something, such as a decorator, a base
            class or an annotation.
        :return: The last name it refers to, ignoring subscripts and calls, ``None``
            when it is no reference.
        """
        if isinstance(expression, ast.Name):
            return expression.id
        if isinstance(expression, ast.Attribute):
            return expression.attr
        if isinstance(expression, ast.Subscript):
            return PythonSource.referenced_name(expression.value)
        if isinstance(expression, ast.Call):
            return PythonSource.referenced_name(expression.func)
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            return expression.value.split("[")[0].split(".")[-1].strip()
        return None

    @staticmethod
    def annotated_parameters(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> dict[str, str]:
        """
        :param function: A function definition.
        :return: The class each parameter is annotated with, for the parameters the
            function's body never assigns to or deletes.
        """
        arguments = function.args
        parameters = [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]
        assigned = {
            node.id
            for statement in function.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load)
        }
        return {
            parameter.arg: annotated
            for parameter in parameters
            if parameter.annotation is not None
            and parameter.arg not in assigned
            and (declared := AnnotatedType.from_annotation(parameter.annotation))
            and (annotated := declared.plain_class)
        }

    @staticmethod
    def is_identifier(token: tokenize.TokenInfo) -> bool:
        """
        :param token: A token of a Python file.
        :return: Whether it is a name that is not a keyword.
        """
        return token.type == tokenize.NAME and not keyword.iskeyword(token.string)

    def definition_span(self, name: str) -> LineSpan:
        """
        :param name: A name a top-level statement of the file defines.
        :return: The lines of that statement, its decorators and, for an assignment,
            the docstring right below it included.
        """
        body = self.tree.body
        index, statement = next(
            (index, statement)
            for index, statement in enumerate(body)
            if name in self.names_defined_by(statement)
        )
        decorators = (
            statement.decorator_list
            if isinstance(
                statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            )
            else []
        )
        first = min([statement.lineno, *(node.lineno for node in decorators)])
        last = statement
        if (
            isinstance(statement, ast.Assign | ast.AnnAssign)
            and index + 1 < len(body)
            and self.is_documentation(body[index + 1])
        ):
            last = body[index + 1]
        return LineSpan(first, last.end_lineno or last.lineno)

    @cached_property
    def lines(self) -> tuple[str, ...]:
        """
        The file's lines, without their line ends.
        """
        return tuple(self.text.splitlines())

    def header_above(self, span: LineSpan) -> LineSpan | None:
        """
        :param span: Lines of the file.
        :return: The section header opening right above them, past blank lines,
            ``None`` when there is none.
        """
        header = span.first - 1
        while header > 0 and not self.lines[header - 1].strip():
            header -= 1
        if header == 0 or not self.lines[header - 1].startswith(SECTION_HEADER):
            return None
        return LineSpan(header, header)

    def lines_of(self, span: LineSpan) -> str:
        """
        :param span: Lines of the file.
        :return: Their text.
        """
        return "\n".join(self.text.splitlines()[span.first - 1 : span.last]) + "\n"

    @cached_property
    def non_blank_lines(self) -> tuple[str, ...]:
        """
        The file's lines that hold more than whitespace.
        """
        return tuple(line for line in self.text.splitlines() if line.strip())

    def without(self, spans: tuple[LineSpan, ...]) -> PythonSource:
        """
        :param spans: Lines of the file.
        :return: The file with those lines emptied, every other line keeping its number.
        """
        removed = {line for span in spans for line in range(span.first, span.last + 1)}
        kept = [
            "" if number in removed else text
            for number, text in enumerate(self.text.splitlines(), start=1)
        ]
        return PythonSource.from_text("\n".join(kept) + "\n", self.package)

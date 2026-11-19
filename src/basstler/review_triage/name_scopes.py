"""
The names each scope of a Python file binds, and what each binding gives them.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass, field

from basstler.review_triage.renames import DOTTED_NAME_SEPARATOR

STAR_IMPORT = "*"
"""
The name a ``from module import *`` imports.
"""

COMPREHENSION_TYPES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
"""
The expressions whose loop variables a scope of their own binds.
"""

SCOPED_FIELDS: dict[type[ast.AST], frozenset[str]] = {
    ast.Module: frozenset({"body"}),
    ast.ClassDef: frozenset({"body"}),
    ast.FunctionDef: frozenset({"body"}),
    ast.AsyncFunctionDef: frozenset({"body"}),
    ast.Lambda: frozenset({"body"}),
    **dict.fromkeys(
        COMPREHENSION_TYPES, frozenset({"elt", "key", "value", "generators"})
    ),
}
"""
For each node opening a scope, the fields holding the code that runs in it.
"""

# %% bindings


class NameBinding:
    """
    One way a scope binds a name, telling what the name refers to afterwards.
    """


@dataclass(frozen=True)
class AssignedValue(NameBinding):
    """
    ``name = value``: the name refers to the value.
    """

    value: ast.expr
    """
    The expression assigned.
    """


@dataclass(frozen=True)
class IteratedElement(NameBinding):
    """
    ``for name in iterable``: the name refers to an element of the iterable.
    """

    iterable: ast.expr
    """
    The expression iterated over.
    """


@dataclass(frozen=True)
class DeclaredType(NameBinding):
    """
    An annotated parameter or assignment, or an ``except`` clause: the name refers to an
    instance of what the annotation declares.
    """

    annotation: ast.expr
    """
    The annotation, or the exception class caught.
    """


@dataclass(frozen=True)
class DefinitionReference(NameBinding):
    """
    A binding making the name refer to a class or function the commit defines.
    """

    defined_name: str
    """
    The name the class or function is defined under.
    """


@dataclass(frozen=True)
class ImportedDefinition(DefinitionReference):
    """
    An import of a module's member: the name refers to a definition of the commit found
    by its name.
    """


@dataclass(frozen=True)
class ImportedMember(ImportedDefinition):
    """
    ``from module import member``: the name refers to that member of that module.
    """

    statement: ast.ImportFrom
    """
    The import statement binding it, whose module may be relative.
    """


@dataclass(frozen=True)
class ImportedModule(NameBinding):
    """
    ``import module``: the name refers to a module.
    """

    module: str
    """
    The dotted path of the module the name refers to.
    """


@dataclass(frozen=True)
class LocalDefinition(DefinitionReference):
    """
    A ``class`` or ``def`` statement: the name refers to a definition of the file
    itself.
    """


@dataclass(frozen=True)
class UnknownValue(NameBinding):
    """
    Any other binding: what the name refers to is not followed.
    """


# %% scopes


@dataclass(frozen=True)
class NameScope:
    """
    The names one module, class body, function, lambda or comprehension binds.
    """

    bindings: dict[str, tuple[NameBinding, ...]] = field(default_factory=dict)
    """
    Every binding of each name the scope binds, in no particular order.
    """

    class_body: bool = False
    """
    Whether it is a class body, whose names the scopes nested in it do not see.
    """

    star_imports: tuple[ast.ImportFrom, ...] = ()
    """
    Its ``from module import *`` statements, which may bind names they do not list.
    """

    @property
    def imports_everything(self) -> bool:
        """
        Whether a star import may bind names the scope does not list.
        """
        return bool(self.star_imports)

    @classmethod
    def opened_by(cls, node: ast.AST) -> NameScope:
        """
        :param node: A node of a type :data:`SCOPED_FIELDS` lists.
        :return: The scope its code runs in.
        """
        if isinstance(node, COMPREHENSION_TYPES):
            return cls(ScopeReader().loop_bindings(node.generators))
        reader = ScopeReader()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            reader.read_parameters(node.args)
        body = node.body if isinstance(node.body, list) else [node.body]
        reader.read(body)
        return cls(
            reader.bindings_by_name(),
            class_body=isinstance(node, ast.ClassDef),
            star_imports=tuple(reader.star_imports),
        )

    @classmethod
    def from_imports(cls, tree: ast.Module) -> NameScope:
        """
        :param tree: A whole file.
        :return: The names its imports bind, in whichever scope they are.
        """
        reader = ScopeReader()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                reader.bindings.extend(reader.named_bindings(node))
        return cls(reader.bindings_by_name(), star_imports=tuple(reader.star_imports))


@dataclass
class ScopeReader:
    """
    Collects the bindings of the code of one scope, leaving out the nested scopes.
    """

    bindings: list[tuple[str, NameBinding]] = field(default_factory=list)
    """
    Each name bound so far, with how.
    """

    star_imports: list[ast.ImportFrom] = field(default_factory=list)
    """
    The ``from module import *`` statements found so far.
    """

    def bindings_by_name(self) -> dict[str, tuple[NameBinding, ...]]:
        """
        :return: :attr:`bindings` grouped by name.
        """
        grouped: dict[str, list[NameBinding]] = {}
        for name, binding in self.bindings:
            grouped.setdefault(name, []).append(binding)
        return {name: tuple(bindings) for name, bindings in grouped.items()}

    def read_parameters(self, arguments: ast.arguments) -> None:
        """
        Bind each parameter to an instance of its annotation, the collecting ``*`` and
        ``**`` parameters to an unknown value.

        :param arguments: The parameters of a function or lambda.
        """
        for parameter in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ):
            annotation = parameter.annotation
            self.bindings.append(
                (
                    parameter.arg,
                    UnknownValue() if annotation is None else DeclaredType(annotation),
                )
            )
        for collecting in (arguments.vararg, arguments.kwarg):
            if collecting is not None:
                self.bindings.append((collecting.arg, UnknownValue()))

    def loop_bindings(
        self, generators: list[ast.comprehension]
    ) -> dict[str, tuple[NameBinding, ...]]:
        """
        :param generators: The ``for`` clauses of a comprehension.
        :return: The bindings of their loop variables.
        """
        for generator in generators:
            target = generator.target
            if isinstance(target, ast.Name) and not generator.is_async:
                self.bindings.append((target.id, IteratedElement(generator.iter)))
                continue
            self.bindings.extend(
                (node.id, UnknownValue())
                for node in ast.walk(target)
                if isinstance(node, ast.Name)
            )
        return self.bindings_by_name()

    def read(self, code: list[ast.AST]) -> None:
        """
        Collect the bindings the code makes in its own scope.

        :param code: The code of the scope.
        """
        known: dict[ast.Name, NameBinding] = {}
        for node in self.scope_nodes(code):
            known |= self.known_bindings(node)
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
                self.bindings.append((node.id, known.get(node, UnknownValue())))
            else:
                self.bindings.extend(self.named_bindings(node))
        self.bindings.extend(
            (name, UnknownValue())
            for node in self.nested_statements(code)
            if isinstance(node, (ast.Global, ast.Nonlocal))
            for name in node.names
        )

    @staticmethod
    def nested_statements(code: list[ast.AST]) -> Iterator[ast.AST]:
        """
        :param code: Some code.
        :return: Every node of it that is no expression, nested scopes included;
            no expression holds a statement.
        """
        pending = list(code)
        while pending:
            node = pending.pop()
            if isinstance(node, ast.expr):
                continue
            yield node
            pending.extend(ast.iter_child_nodes(node))

    @staticmethod
    def scope_nodes(code: list[ast.AST]) -> Iterator[ast.AST]:
        """
        :param code: The code of a scope.
        :return: Every node of it that binds names in the scope, each before its
            children: the nested scopes left out but for the assignment expressions of
            comprehensions.
        """
        pending = list(code)
        while pending:
            node = pending.pop()
            yield node
            if isinstance(node, COMPREHENSION_TYPES):
                pending.extend(
                    child
                    for child in ast.iter_child_nodes(node)
                    if not isinstance(child, ast.comprehension)
                )
                pending.extend(
                    part
                    for generator in node.generators
                    for part in (generator.iter, *generator.ifs)
                )
                continue
            scoped = SCOPED_FIELDS.get(type(node), frozenset())
            pending.extend(
                child
                for field_name, value in ast.iter_fields(node)
                if field_name not in scoped
                for child in (value if isinstance(value, list) else [value])
                if isinstance(child, ast.AST)
            )

    @staticmethod
    def known_bindings(node: ast.AST) -> dict[ast.Name, NameBinding]:
        """
        :param node: A node of the scope.
        :return: What it binds each name it assigns directly to; an assignment
            expression's value is not followed, since it may use a comprehension's
            loop variables.
        """
        if isinstance(node, ast.Assign):
            return {
                target: AssignedValue(node.value)
                for target in node.targets
                if isinstance(target, ast.Name)
            }
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return {node.target: DeclaredType(node.annotation)}
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            return {node.target: IteratedElement(node.iter)}
        return {}

    def named_bindings(self, node: ast.AST) -> Iterator[tuple[str, NameBinding]]:
        """
        :param node: A node of the scope other than a name.
        :return: The names it binds by spelling them, with how.
        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, LocalDefinition(node.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == STAR_IMPORT:
                    self.star_imports.append(node)
                    continue
                yield alias.asname or alias.name, ImportedMember(alias.name, node)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is not None:
                    yield alias.asname, ImportedModule(alias.name)
                    continue
                top_level = alias.name.split(DOTTED_NAME_SEPARATOR)[0]
                yield top_level, ImportedModule(top_level)
        elif isinstance(node, ast.ExceptHandler) and node.name is not None:
            caught = node.type
            yield (
                node.name,
                DeclaredType(caught)
                if isinstance(caught, (ast.Name, ast.Attribute))
                else UnknownValue(),
            )
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name is not None:
            yield node.name, UnknownValue()
        elif isinstance(node, ast.MatchMapping) and node.rest is not None:
            yield node.rest, UnknownValue()

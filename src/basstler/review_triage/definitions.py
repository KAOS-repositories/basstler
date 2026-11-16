"""
The functions, methods and classes a commit defines, read once from each file into
small records holding only what deciding a call's binding needs.
"""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cached_property

from basstler.review_triage.python_source import AnnotatedType, PythonSource

# %% names the reading recognises


class DataclassName(StrEnum):
    """
    The names of the standard library's dataclass machinery a class definition uses.
    """

    MODULE = "dataclasses"
    """
    The module that provides it.
    """

    DECORATOR = "dataclass"
    """
    The decorator that generates a class's initializer from its fields.
    """

    FIELD = "field"
    """
    The function that configures one field.
    """

    KEYWORD_ONLY = "kw_only"
    """
    The option that makes fields keyword-only.
    """

    INITIALIZED = "init"
    """
    The option that decides whether the initializer takes a field, or is generated.
    """

    KEYWORD_ONLY_MARKER = "KW_ONLY"
    """
    The annotation after which every field is keyword-only.
    """

    CLASS_VARIABLE = "ClassVar"
    """
    The annotation of a class attribute that is not a field.
    """


PROPERTY_DECORATORS = frozenset({"property", "cached_property"})
"""
The decorators that make a method an attribute holding what it returns.
"""

TYPE_VARIABLE = "TypeVar"
"""
The class whose instances are type variables.
"""

CLASS_OBJECT_ANNOTATIONS = frozenset({"type", "Type"})
"""
The annotations of a parameter taking a class rather than an instance.
"""

# %% the conventional receiver names


class ReceiverName(StrEnum):
    """
    The names a method's code conventionally refers to what it is called on by.
    """

    INSTANCE = "self"
    """
    The instance an instance method is called on.
    """

    CLASS = "cls"
    """
    The class a class method is called on.
    """

    PARENT = "super"
    """
    The function giving access to the methods a class inherits.
    """


# %% the records


@dataclass(frozen=True, slots=True)
class FunctionDefinition:
    """
    A function or method, as far as a call's binding depends on it.
    """

    name: str
    """
    The function's name.
    """

    owner: str | None
    """
    The name of the class whose body defines it directly, ``None`` outside a class.
    """

    decorators: tuple[str | None, ...]
    """
    The names its decorators are referred to by, ``None`` for one that is no plain
    reference.
    """

    parameters: tuple[str, ...]
    """
    The names of the parameters an argument can be passed to positionally, in order,
    the instance or class of a method included.
    """

    positional_only: int
    """
    How many of the first parameters can only be passed positionally.
    """

    variadic: bool
    """
    Whether further positional arguments are collected by a ``*`` parameter.
    """

    returns_its_argument: bool
    """
    Whether it is an undecorated function of one parameter that only returns it.
    """

    return_type: AnnotatedType | None = None
    """
    What its return annotation declares, ``None`` when it allows no single class.
    """

    class_argument_parameter: str | None = None
    """
    The parameter annotated ``type[T]`` whose argument's class it returns an instance
    of, its return annotation being the type variable ``T``.
    """


@dataclass(frozen=True, slots=True)
class DataclassField:
    """
    One field a dataclass's generated initializer takes.
    """

    name: str
    """
    The field's name, the initializer's parameter.
    """

    keyword_only: bool
    """
    Whether the parameter can only be passed by keyword.
    """


@dataclass(frozen=True, slots=True)
class AttributeType:
    """
    The class an attribute of a class's instances is declared to hold.
    """

    name: str
    """
    The attribute's name.
    """

    declared_type: AnnotatedType | None
    """
    What its annotation declares, ``None`` when it allows no single class.
    """


@dataclass(frozen=True, slots=True)
class ClassDefinition:
    """
    A class, as far as a call of it or of its methods depends on it.
    """

    name: str
    """
    The class's name.
    """

    decorators: tuple[str | None, ...]
    """
    The names its decorators are referred to by, ``None`` for one that is no plain
    reference.
    """

    bases: tuple[str | None, ...]
    """
    The names its base classes are referred to by, ``None`` for one that is no plain
    reference.
    """

    customized: bool
    """
    Whether its definition passes keywords, such as a metaclass, that may change how
    it is called.
    """

    methods: tuple[FunctionDefinition, ...]
    """
    The methods its body defines.
    """

    dataclass_fields: tuple[DataclassField, ...] | None
    """
    The fields its standard dataclass decorator generates the initializer from, in
    order, empty when it is no dataclass and ``None`` when they cannot be read.
    """

    is_dataclass: bool
    """
    Whether the standard dataclass decorator generates its initializer.
    """

    attribute_types: tuple[AttributeType, ...]
    """
    The attributes it declares a class for: in its body, on ``self`` in its methods
    or as the return of its properties.
    """

    def method(self, name: str) -> FunctionDefinition | None:
        """
        :param name: The name of a method.
        :return: The method of that name the class defines itself, ``None`` when it
            defines none.
        """
        return next((method for method in self.methods if method.name == name), None)


Definition = FunctionDefinition | ClassDefinition
"""
Anything a call may refer to by name.
"""


# %% reading a file


@dataclass(frozen=True)
class DefinitionReader:
    """
    Reads the definitions of one Python file into records.
    """

    source: PythonSource
    """
    The file read.
    """

    def definitions(self) -> Iterator[Definition]:
        """
        :return: Every function, method and class the file defines, at any depth.
        """
        owners = {
            statement: node.name
            for node in ast.walk(self.source.tree)
            if isinstance(node, ast.ClassDef)
            for statement in node.body
        }
        for node in ast.walk(self.source.tree):
            if isinstance(node, ast.ClassDef):
                yield self.class_definition(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield self.function_definition(node, owners.get(node))

    @cached_property
    def type_variables(self) -> frozenset[str]:
        """
        The names the file's top level binds to a :class:`typing.TypeVar`.
        """
        return frozenset(
            target.id
            for statement in self.source.tree.body
            if isinstance(statement, ast.Assign)
            and isinstance(statement.value, ast.Call)
            and PythonSource.referenced_name(statement.value.func) == TYPE_VARIABLE
            for target in statement.targets
            if isinstance(target, ast.Name)
        )

    def function_definition(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, owner: str | None
    ) -> FunctionDefinition:
        """
        :param node: A function definition.
        :param owner: The name of the class whose body holds it.
        :return: Its record.
        """
        arguments = node.args
        body = [
            statement
            for statement in node.body
            if not PythonSource.is_documentation(statement)
        ]
        single_parameter = (
            not arguments.posonlyargs
            and len(arguments.args) == 1
            and not arguments.kwonlyargs
            and arguments.vararg is None
            and arguments.kwarg is None
        )
        return FunctionDefinition(
            name=node.name,
            owner=owner,
            decorators=tuple(map(PythonSource.referenced_name, node.decorator_list)),
            parameters=tuple(
                parameter.arg for parameter in (*arguments.posonlyargs, *arguments.args)
            ),
            positional_only=len(arguments.posonlyargs),
            variadic=arguments.vararg is not None,
            returns_its_argument=(
                owner is None
                and not node.decorator_list
                and single_parameter
                and len(body) == 1
                and isinstance(body[0], ast.Return)
                and isinstance(body[0].value, ast.Name)
                and body[0].value.id == arguments.args[0].arg
            ),
            return_type=(
                None
                if node.returns is None
                else AnnotatedType.from_annotation(
                    node.returns, self.generic_names(node)
                )
            ),
            class_argument_parameter=self.class_argument_parameter(node),
        )

    def generic_names(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> frozenset[str]:
        """
        :param node: A function or class definition.
        :return: The type variables its annotations may use.
        """
        return self.type_variables | {variable.name for variable in node.type_params}

    def class_argument_parameter(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str | None:
        """
        :param node: A function definition.
        :return: The parameter annotated ``type[T]`` when it returns the type variable
            ``T``.
        """
        if not isinstance(node.returns, ast.Name):
            return None
        variable = node.returns.id
        if variable not in self.generic_names(node):
            return None
        arguments = node.args
        return next(
            (
                parameter.arg
                for parameter in (
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                )
                if isinstance(parameter.annotation, ast.Subscript)
                and PythonSource.referenced_name(parameter.annotation.value)
                in CLASS_OBJECT_ANNOTATIONS
                and isinstance(parameter.annotation.slice, ast.Name)
                and parameter.annotation.slice.id == variable
            ),
            None,
        )

    def class_definition(self, node: ast.ClassDef) -> ClassDefinition:
        """
        :param node: A class definition.
        :return: Its record.
        """
        decorator = self.dataclass_decorator(node)
        return ClassDefinition(
            name=node.name,
            decorators=tuple(map(PythonSource.referenced_name, node.decorator_list)),
            bases=tuple(map(PythonSource.referenced_name, node.bases)),
            customized=bool(node.keywords),
            methods=tuple(
                self.function_definition(statement, node.name)
                for statement in node.body
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            ),
            dataclass_fields=(
                () if decorator is None else self.dataclass_fields(node, decorator)
            ),
            is_dataclass=decorator is not None,
            attribute_types=tuple(self.attribute_types(node)),
        )

    def attribute_types(self, node: ast.ClassDef) -> Iterator[AttributeType]:
        """
        :param node: A class definition.
        :return: Every attribute declaration of the class, with what it declares.
        """
        generic = self.generic_names(node)
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(
                statement.target, ast.Name
            ):
                yield AttributeType(
                    statement.target.id,
                    AnnotatedType.from_annotation(statement.annotation, generic),
                )
            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if PROPERTY_DECORATORS & {
                PythonSource.referenced_name(decorator)
                for decorator in statement.decorator_list
            }:
                yield AttributeType(
                    statement.name,
                    statement.returns
                    and AnnotatedType.from_annotation(statement.returns, generic),
                )
            for assignment in ast.walk(statement):
                if (
                    isinstance(assignment, ast.AnnAssign)
                    and isinstance(assignment.target, ast.Attribute)
                    and isinstance(assignment.target.value, ast.Name)
                    and assignment.target.value.id == ReceiverName.INSTANCE
                ):
                    yield AttributeType(
                        assignment.target.attr,
                        AnnotatedType.from_annotation(assignment.annotation, generic),
                    )

    def dataclass_decorator(self, node: ast.ClassDef) -> ast.expr | None:
        """
        :param node: A class definition.
        :return: Its standard dataclass decorator, ``None`` when it has none.
        """
        return next(
            (
                decorator
                for decorator in node.decorator_list
                if self.source.import_bindings.refers_to(
                    decorator.func if isinstance(decorator, ast.Call) else decorator,
                    DataclassName.MODULE,
                    DataclassName.DECORATOR,
                )
            ),
            None,
        )

    @staticmethod
    def dataclass_fields(
        node: ast.ClassDef, decorator: ast.expr
    ) -> tuple[DataclassField, ...] | None:
        """
        :param node: A dataclass definition.
        :param decorator: Its dataclass decorator.
        :return: The fields it declares itself, in order, ``None`` when they cannot
            be read.
        """
        options = (
            DefinitionReader.literal_options(decorator)
            if isinstance(decorator, ast.Call)
            else {}
        )
        if options is None:
            return None
        return DefinitionReader.own_fields(node, options)

    @staticmethod
    def literal_options(call: ast.Call) -> dict[str, bool] | None:
        """
        :param call: A call of the dataclass decorator or of its field function.
        :return: The options deciding which fields the initializer takes and how,
            ``None`` when one of them is not a literal boolean.
        """
        options: dict[str, bool] = {}
        for keyword in call.keywords:
            if keyword.arg is None:
                return None
            if keyword.arg not in (
                DataclassName.INITIALIZED,
                DataclassName.KEYWORD_ONLY,
            ):
                continue
            if not isinstance(keyword.value, ast.Constant) or not isinstance(
                keyword.value.value, bool
            ):
                return None
            options[keyword.arg] = keyword.value.value
        return options

    @staticmethod
    def own_fields(
        node: ast.ClassDef, options: dict[str, bool]
    ) -> tuple[DataclassField, ...] | None:
        """
        :param node: A dataclass definition.
        :param options: The options of its decorator.
        :return: The fields it declares itself, in order, ``None`` when it generates
            no initializer or a field cannot be read.
        """
        if not options.get(DataclassName.INITIALIZED, True):
            return None
        keyword_only = options.get(DataclassName.KEYWORD_ONLY, False)
        fields: list[DataclassField] = []
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(
                statement.target, ast.Name
            ):
                continue
            annotation = PythonSource.referenced_name(statement.annotation)
            if annotation == DataclassName.CLASS_VARIABLE:
                continue
            if annotation == DataclassName.KEYWORD_ONLY_MARKER:
                keyword_only = True
                continue
            field_options: dict[str, bool] | None = {}
            if (
                isinstance(statement.value, ast.Call)
                and PythonSource.referenced_name(statement.value.func)
                == DataclassName.FIELD
            ):
                field_options = DefinitionReader.literal_options(statement.value)
            if field_options is None:
                return None
            if field_options.get(DataclassName.INITIALIZED, True):
                fields.append(
                    DataclassField(
                        statement.target.id,
                        field_options.get(DataclassName.KEYWORD_ONLY, keyword_only),
                    )
                )
        return tuple(fields)


# %% where definitions are found


class DefinitionSearch(ABC):
    """
    Finds the Python files of one commit by what they hold, and reads them.
    """

    @abstractmethod
    def files_defining(self, names: frozenset[str]) -> tuple[str, ...]:
        """
        :param names: Names of functions, methods or classes.
        :return: A key for every file defining one of them; files defining none may be
            among them.
        """

    @abstractmethod
    def files_subclassing(self, name: str) -> tuple[str, ...]:
        """
        :param name: The name of a class.
        :return: A key for every file defining a class that names it among its bases;
            files defining none may be among them.
        """

    @abstractmethod
    def texts_of(self, files: tuple[str, ...]) -> dict[str, str]:
        """
        :param files: Keys of files this search found.
        :return: The content of each, by its key.
        """


@dataclass(frozen=True)
class SourceDefinitions(DefinitionSearch):
    """
    Searches a fixed set of Python file contents, each keyed by its position.
    """

    texts: tuple[str, ...] = ()
    """
    The contents searched.
    """

    def files_defining(self, names: frozenset[str]) -> tuple[str, ...]:
        return tuple(map(str, range(len(self.texts))))

    def files_subclassing(self, name: str) -> tuple[str, ...]:
        return tuple(map(str, range(len(self.texts))))

    def texts_of(self, files: tuple[str, ...]) -> dict[str, str]:
        return {file: self.texts[int(file)] for file in files}


# %% the index


@dataclass
class DefinitionIndex:
    """
    The definitions of one commit by name and by the classes they inherit from, each
    file read once and each search made once.
    """

    search: DefinitionSearch = field(default_factory=SourceDefinitions)
    """
    Where the definitions are found.
    """

    by_file: dict[str, tuple[Definition, ...]] = field(default_factory=dict)
    """
    The definitions of each file read so far, by its key.
    """

    by_name: dict[str, tuple[Definition, ...]] = field(default_factory=dict)
    """
    Every definition of each name looked up so far.
    """

    direct_subclasses: dict[str, tuple[ClassDefinition, ...]] = field(
        default_factory=dict
    )
    """
    The classes naming each class looked up so far among their bases.
    """

    def file_definitions(self, files: tuple[str, ...]) -> Iterator[Definition]:
        """
        :param files: Keys of files the search found.
        :return: Every definition they hold, the files not read yet read together.
        """
        unread = tuple(
            dict.fromkeys(file for file in files if file not in self.by_file)
        )
        for file, text in self.search.texts_of(unread).items():
            self.by_file[file] = tuple(
                DefinitionReader(PythonSource(text)).definitions()
            )
        for file in files:
            yield from self.by_file[file]

    def load(self, names: frozenset[str]) -> None:
        """
        Find the definitions of every name not looked up yet, in one search.

        :param names: Names of functions, methods or classes.
        """
        missing = names - self.by_name.keys()
        if not missing:
            return
        found: dict[str, list[Definition]] = {name: [] for name in missing}
        files = self.search.files_defining(frozenset(missing))
        for definition in self.file_definitions(files):
            if definition.name in found:
                found[definition.name].append(definition)
        self.by_name |= {name: tuple(named) for name, named in found.items()}

    def definitions_of(self, name: str) -> tuple[Definition, ...]:
        """
        :param name: The name of a function, method or class.
        :return: Every definition of it.
        """
        self.load(frozenset({name}))
        return self.by_name[name]

    def classes_named(self, name: str) -> tuple[ClassDefinition, ...]:
        """
        :param name: The name of a class.
        :return: Every class definition of it.
        """
        return tuple(
            definition
            for definition in self.definitions_of(name)
            if isinstance(definition, ClassDefinition)
        )

    def is_identity(self, name: str) -> bool:
        """
        :param name: The name a decorator is referred to by.
        :return: Whether every definition of it is a plain function returning its only
            argument, at least one being found.
        """
        definitions = self.definitions_of(name)
        return bool(definitions) and all(
            isinstance(definition, FunctionDefinition)
            and definition.returns_its_argument
            for definition in definitions
        )

    # %%% the class hierarchy

    def subclasses_of(self, name: str) -> list[ClassDefinition]:
        """
        :param name: The name of a class.
        :return: Every class inheriting from a class of that name, at any depth.
        """
        found: list[ClassDefinition] = []
        visited = {name}
        pending = [name]
        while pending:
            current = pending.pop()
            if current not in self.direct_subclasses:
                files = self.search.files_subclassing(current)
                self.direct_subclasses[current] = tuple(
                    definition
                    for definition in self.file_definitions(files)
                    if isinstance(definition, ClassDefinition)
                    and current in definition.bases
                )
            for subclass in self.direct_subclasses[current]:
                found.append(subclass)
                if subclass.name not in visited:
                    visited.add(subclass.name)
                    pending.append(subclass.name)
        return found

    def ancestors_of(self, classes: list[ClassDefinition]) -> list[ClassDefinition]:
        """
        :param classes: Class definitions.
        :return: Every class of the commit they inherit from, at any depth.
        """
        found: list[ClassDefinition] = []
        visited: set[str] = set()
        pending = [base for definition in classes for base in definition.bases if base]
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            for definition in self.classes_named(current):
                found.append(definition)
                pending.extend(base for base in definition.bases if base)
        return found

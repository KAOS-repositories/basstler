"""
What the names and attributes of one commit's code are proven to refer to, read from its
source alone.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import importlib.util
import sys
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import PurePosixPath

from basstler.review_triage.commit_tree import PACKAGE_INITIALIZER, CommitModules
from basstler.review_triage.name_scopes import (
    AssignedValue,
    DeclaredType,
    ImportedMember,
    ImportedModule,
    LocalDefinition,
    NameBinding,
    NameScope,
)
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import (
    DOTTED_NAME_SEPARATOR,
    ClassAttribute,
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


@dataclass(frozen=True)
class StandardLibraryMember:
    """
    A member of a module of Python's standard library, the builtins included.
    """

    module: str
    """
    The module's dotted path.
    """

    member_name: str
    """
    The name the module binds.
    """

    @cached_property
    def value(self) -> object:
        """
        The member itself, ``None`` when the module does not bind it or is not installed
        on this platform.
        """
        root = self.module.partition(DOTTED_NAME_SEPARATOR)[0]
        if importlib.util.find_spec(root) is None:
            return None
        return getattr(importlib.import_module(self.module), self.member_name, None)


@dataclass(frozen=True)
class ClassInstance:
    """
    The receiver of a method of a module's top-level class: an instance of the class, or
    the class itself in a class method.
    """

    owner: ModuleMember
    """
    The class whose method receives it.
    """


Referent = (
    ModuleMember | ModuleObject | ClassAttribute | ClassInstance | StandardLibraryMember
)
"""
What a name or an attribute is proven to refer to.
"""

OWN_MEMBER_BINDINGS = (LocalDefinition, AssignedValue, DeclaredType)
"""
The bindings that make a module's top-level name a member the module itself defines.
"""

BUILTINS_MODULE = builtins.__name__
"""
The module binding the names no module has to import.
"""

OBJECT = StandardLibraryMember(BUILTINS_MODULE, object.__name__)
"""
The class every class inherits from.
"""

PROPERTY_ACCESSORS = frozenset({"getter", "setter", "deleter"})
"""
The attributes of a property that decorate another of its accessor methods.
"""

RECEIVING_DECORATORS = frozenset(
    {
        StandardLibraryMember(BUILTINS_MODULE, property.__name__),
        StandardLibraryMember(BUILTINS_MODULE, classmethod.__name__),
        StandardLibraryMember("abc", "abstractmethod"),
        StandardLibraryMember("functools", "cached_property"),
        StandardLibraryMember("typing", "override"),
    }
)
"""
The decorators that leave a method's first parameter its receiver.
"""

SUPER = StandardLibraryMember(BUILTINS_MODULE, super.__name__)
"""
The function reading the attributes a class inherits.
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

    def overrides_star_imports(self, name: str) -> bool:
        """
        :param name: A name the module's top level binds.
        :return: Whether its one binding is a top-level import following every star
            import, with nothing but imports running before it, so that every use of
            the name sees that import.
        """
        bindings = self.scope.bindings.get(name, ())
        if len(bindings) != 1 or not isinstance(bindings[0], ImportedMember):
            return False
        body = self.source.tree.body
        statement = bindings[0].statement
        if statement not in body:
            return False
        preceding = body[: body.index(statement)]
        return all(star in preceding for star in self.scope.star_imports) and all(
            isinstance(node, (ast.Import, ast.ImportFrom))
            or PythonSource.is_documentation(node)
            for node in preceding
        )

    @cached_property
    def scope(self) -> NameScope:
        """
        The names its top level binds.
        """
        return NameScope.opened_by(self.source.tree)


# %% a class's own attributes


def defined_attribute_names(definition: ast.ClassDef) -> frozenset[str]:
    """
    :param definition: A class definition.
    :return: The names its body binds, and those its methods assign to on their first
        parameter.
    """
    names = set(NameScope.opened_by(definition).bindings)
    for method in definition.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        parameters = (*method.args.posonlyargs, *method.args.args)
        if not parameters:
            continue
        receiver = parameters[0].arg
        names.update(
            node.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Attribute)
            and not isinstance(node.ctx, ast.Load)
            and isinstance(node.value, ast.Name)
            and node.value.id == receiver
        )
    return frozenset(names)


def base_words(definition: ast.ClassDef) -> frozenset[str]:
    """
    :param definition: A class definition.
    :return: Every name its bases and keywords spell.
    """
    return frozenset(
        word
        for part in (*definition.bases, *definition.keywords)
        for node in ast.walk(part)
        for word in (
            (node.id,)
            if isinstance(node, ast.Name)
            else (node.attr,)
            if isinstance(node, ast.Attribute)
            else ()
        )
    )


# %% resolving names across the commit


@dataclass
class MemberResolver:
    """
    Proves what the names and attributes of one commit's modules refer to, following
    imports from module to module and attributes through class hierarchies, each module
    read once.
    """

    modules: CommitModules
    """
    The commit's modules.
    """

    read_modules: dict[str, ModuleNames | None] = field(default_factory=dict)
    """
    Each module read so far, ``None`` when no single parsable file is that module.
    """

    read_files: dict[str, ast.Module | None] = field(default_factory=dict)
    """
    Each file read so far by its key, ``None`` when it does not parse.
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

    def is_standard_library(self, module: str) -> bool:
        """
        :param module: A dotted module path.
        :return: Whether it is a module of the standard library no file of the commit
            shadows.
        """
        root = module.partition(DOTTED_NAME_SEPARATOR)[0]
        return root in sys.stdlib_module_names and root not in self.package_roots

    @cached_property
    def package_roots(self) -> frozenset[str]:
        """
        The first component of the dotted path of every module of the commit.
        """
        return frozenset(
            module.partition(DOTTED_NAME_SEPARATOR)[0]
            for module in self.modules.module_files
        )

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
        if self.is_standard_library(module):
            return StandardLibraryMember(module, member_name)
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
        :return: What the name refers to, a builtin when the module binds it nowhere,
            ``None`` when it is not proven: bound more than once, possibly by a star
            import, or also a submodule's name.
        """
        scope = names.scope
        submodule = f"{names.module}{DOTTED_NAME_SEPARATOR}{name}"
        is_submodule = submodule in self.modules.module_files
        bindings = scope.bindings.get(name, ())
        if scope.imports_everything and not names.overrides_star_imports(name):
            return None
        if not bindings:
            if is_submodule:
                return ModuleObject(submodule)
            if hasattr(builtins, name):
                return StandardLibraryMember(BUILTINS_MODULE, name)
            return None
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

    def module_expression_referent(
        self, names: ModuleNames, expression: ast.expr
    ) -> Referent | None:
        """
        :param names: A module.
        :param expression: A name or a chain of attributes its top level evaluates,
            subscripts and calls looked through.
        :return: What it refers to, ``None`` when it is not proven.
        """
        if isinstance(expression, (ast.Subscript, ast.Call)):
            inner = (
                expression.value
                if isinstance(expression, ast.Subscript)
                else expression.func
            )
            return self.module_expression_referent(names, inner)
        if isinstance(expression, ast.Name):
            return self.top_level_referent(names, expression.id)
        if not isinstance(expression, ast.Attribute):
            return None
        return self.attribute_referent(
            self.module_expression_referent(names, expression.value), expression.attr
        )

    def attribute_referent(
        self, value: Referent | None, attribute_name: str
    ) -> Referent | None:
        """
        :param value: What an attribute is read from.
        :param attribute_name: The attribute's name.
        :return: What the attribute refers to, ``None`` when it is not proven.
        """
        if isinstance(value, ModuleObject):
            if self.is_standard_library(value.module):
                return StandardLibraryMember(value.module, attribute_name)
            return self.member_referent(value.module, attribute_name)
        if isinstance(value, ClassInstance):
            return self.attribute_owner(value.owner, attribute_name)
        if isinstance(value, ModuleMember):
            return self.attribute_owner(value, attribute_name)
        return None

    # %%% classes

    def class_definition(self, member: ModuleMember) -> ast.ClassDef | None:
        """
        :param member: A module's top-level name.
        :return: The class it is bound to, ``None`` when it is not proven to be a class
            the module defines once.
        """
        names = self.names_of(member.module)
        if names is None or self.top_level_referent(names, member.member_name) != (
            member
        ):
            return None
        definitions = [
            statement
            for statement in names.source.tree.body
            if isinstance(statement, ast.ClassDef)
            and statement.name == member.member_name
        ]
        return definitions[0] if len(definitions) == 1 else None

    def attribute_names(self, member: ModuleMember) -> frozenset[str]:
        """
        :param member: A class of the commit.
        :return: The attributes it defines itself, none when it is not proven a class.
        """
        definition = self.class_definition(member)
        if definition is None:
            return frozenset()
        return defined_attribute_names(definition)

    def base_referents(self, member: ModuleMember) -> tuple[Referent | None, ...]:
        """
        :param member: A class of the commit.
        :return: What each of its bases refers to, :data:`OBJECT` for a class listing
            none.
        """
        definition = self.class_definition(member)
        names = self.names_of(member.module)
        if definition is None or names is None:
            return (None,)
        if not definition.bases:
            return (OBJECT,)
        return tuple(
            self.module_expression_referent(names, base) for base in definition.bases
        )

    def is_plain_class(self, member: ModuleMember) -> bool:
        """
        :param member: A class of the commit.
        :return: Whether its decorators and keywords, such as a metaclass, all come
            from the standard library, which adds no attribute a class names.
        """
        definition = self.class_definition(member)
        names = self.names_of(member.module)
        if definition is None or names is None:
            return False
        return all(
            isinstance(
                self.module_expression_referent(names, part), StandardLibraryMember
            )
            for part in (
                *definition.decorator_list,
                *(keyword.value for keyword in definition.keywords),
            )
        )

    def attribute_owner(
        self,
        member: ModuleMember,
        attribute_name: str,
        visited: frozenset[ModuleMember] = frozenset(),
    ) -> ClassAttribute | None:
        """
        :param member: A class of the commit.
        :param attribute_name: An attribute read from it or from its instances.
        :param visited: The classes looked through already.
        :return: The class attribute the read refers to, ``None`` when it is not
            proven.
        """
        if member in visited:
            return None
        if attribute_name in self.attribute_names(member):
            return ClassAttribute(member, attribute_name)
        return self.inherited_attribute_owner(member, attribute_name, visited)

    def inherited_attribute_owner(
        self,
        member: ModuleMember,
        attribute_name: str,
        visited: frozenset[ModuleMember] = frozenset(),
    ) -> ClassAttribute | None:
        """
        :param member: A class of the commit.
        :param attribute_name: An attribute it inherits, as ``super()`` reads it.
        :param visited: The classes looked through already.
        :return: The class attribute of its only base class the read refers to,
            ``None`` when it is not proven.
        """
        if not self.is_plain_class(member):
            return None
        bases = [base for base in self.base_referents(member) if base != OBJECT]
        if len(bases) != 1 or not isinstance(bases[0], ModuleMember):
            return None
        return self.attribute_owner(bases[0], attribute_name, visited | {member})

    # %%% class hierarchies

    def defining_ancestors(
        self, member: ModuleMember, attribute_name: str
    ) -> tuple[ModuleMember, ...] | None:
        """
        :param member: A class of the commit.
        :param attribute_name: The name of an attribute.
        :return: Every class of the commit it inherits from that defines the attribute,
            ``None`` when an ancestor is not proven, is not a plain class, or is one of
            the standard library that has the attribute.
        """
        found: list[ModuleMember] = []
        pending = [member]
        visited = {member}
        while pending:
            current = pending.pop()
            if not self.is_plain_class(current):
                return None
            for base in self.base_referents(current):
                if isinstance(base, StandardLibraryMember):
                    if not isinstance(base.value, type) or hasattr(
                        base.value, attribute_name
                    ):
                        return None
                    continue
                if not isinstance(base, ModuleMember) or (
                    self.class_definition(base) is None
                ):
                    return None
                if base in visited:
                    continue
                visited.add(base)
                pending.append(base)
                if attribute_name in self.attribute_names(base):
                    found.append(base)
        return tuple(found)

    def possible_subclasses(
        self, member: ModuleMember
    ) -> list[tuple[ModuleMember | None, ast.ClassDef]] | None:
        """
        :param member: A class of the commit.
        :return: Every class of the commit that may inherit from it at any depth, judged
            by the names its bases spell, with its identity when it is a module's
            top-level class; ``None`` when a file that may define one does not parse.
        """
        found: list[tuple[ModuleMember | None, ast.ClassDef]] = []
        pending = [member.member_name]
        seen_names = {member.member_name}
        seen: set[tuple[str, int]] = set()
        while pending:
            name = pending.pop()
            for key in self.modules.files_subclassing(name):
                tree = self.file_tree(key)
                if tree is None:
                    return None
                for node in ast.walk(tree):
                    if (
                        not isinstance(node, ast.ClassDef)
                        or (key, node.lineno) in seen
                        or name not in base_words(node)
                    ):
                        continue
                    seen.add((key, node.lineno))
                    identity = self.top_level_class(key, tree, node)
                    if identity == member:
                        continue
                    found.append((identity, node))
                    if node.name not in seen_names:
                        seen_names.add(node.name)
                        pending.append(node.name)
        return found

    def file_tree(self, key: str) -> ast.Module | None:
        """
        :param key: A file of the commit.
        :return: Its syntax tree, ``None`` when it does not parse.
        """
        if key not in self.read_files:
            source = PythonSource(self.modules.texts_of((key,))[key])
            self.read_files[key] = source.tree if source.parses else None
        return self.read_files[key]

    def top_level_class(
        self, key: str, tree: ast.Module, node: ast.ClassDef
    ) -> ModuleMember | None:
        """
        :param key: A file of the commit.
        :param tree: Its syntax tree.
        :param node: A class it defines.
        :return: The class, when it is a top-level class of the only file of its
            module.
        """
        if node not in tree.body:
            return None
        path = key.partition(":")[2]
        module = self.modules.module_path(PurePosixPath(path))
        member = ModuleMember(module, node.name)
        return member if self.class_definition(member) is not None else None

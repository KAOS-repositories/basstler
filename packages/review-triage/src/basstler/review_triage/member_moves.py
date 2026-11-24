"""
Finding the class attributes a pull request moves from one class into another, under
their own names, as renames of their dotted paths.
"""

from __future__ import annotations

import ast
import copy
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import auto
from functools import cached_property
from pathlib import PurePosixPath

from basstler.class_property import classproperty
from basstler.git.commit_range import FileVersions
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.commit_tree import (
    FILE_KEY_SEPARATOR,
    MODULE_SUFFIX,
    PACKAGE_INITIALIZER,
    CommitModules,
)
from basstler.review_triage.definition_moves import DefinitionMoveDetection
from basstler.review_triage.module_moves import ModuleMoveDetection
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.referents import (
    MemberResolver,
    ModuleNames,
    ModuleObject,
    Referent,
    StandardLibraryMember,
)
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.renames import (
    DOTTED_NAME_SEPARATOR,
    AttributeMove,
    ClassAttribute,
    ModuleMember,
    RenameDecisions,
    RenameMap,
)

ORDER_DEPENDENT_VALUE = f"{auto.__module__}.{auto.__name__}"
"""
The dotted path of the function whose value depends on the members defined before it.
"""

UNRESOLVED_EXPRESSIONS = (
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.NamedExpr,
    ast.Await,
    ast.Yield,
    ast.YieldFrom,
)
"""
The expressions whose names a class body does not resolve as its own statements do.
"""

# %% what a name of a class body refers to


def dotted_path(referent: Referent | None) -> str | None:
    """
    :param referent: What a name refers to.
    :return: The dotted path it is reached by, ``None`` for the instance of a class or
        an unproven referent.
    """
    if isinstance(referent, ModuleObject):
        return referent.module
    if isinstance(referent, ModuleMember):
        return referent.dotted_path
    if isinstance(referent, StandardLibraryMember):
        return f"{referent.module}{DOTTED_NAME_SEPARATOR}{referent.member_name}"
    if isinstance(referent, ClassAttribute):
        owner = dotted_path(referent.owner)
        return f"{owner}{DOTTED_NAME_SEPARATOR}{referent.attribute_name}"
    return None


def assigned(statement: ast.stmt) -> tuple[str | None, ast.expr | None]:
    """
    :param statement: A statement of a class body.
    :return: The name it assigns and the value, both ``None`` for any statement but an
        assignment of a value to one name.
    """
    if (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
    ):
        return statement.targets[0].id, statement.value
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return statement.target.id, statement.value
    return None, None


@dataclass(frozen=True)
class ClassVersion:
    """
    A module's top-level class as one commit defines it.
    """

    member: ModuleMember
    """
    The class, by its module and name.
    """

    definition: ast.ClassDef
    """
    Its definition.
    """

    resolver: MemberResolver
    """
    What the names of the commit holding it refer to.
    """

    @classmethod
    def from_commit(
        cls, member: ModuleMember, resolver: MemberResolver
    ) -> ClassVersion | None:
        """
        :param member: A module's top-level name.
        :param resolver: What the names of a commit refer to.
        :return: The class the commit defines by that name, ``None`` when it is not
            proven to be one.
        """
        definition = resolver.class_definition(member)
        return None if definition is None else cls(member, definition, resolver)

    @cached_property
    def assignments(self) -> dict[str, ast.expr]:
        """
        The value of each name the class body assigns exactly once.
        """
        values: dict[str, list[ast.expr]] = {}
        for statement in self.definition.body:
            name, value = assigned(statement)
            if name is not None and value is not None:
                values.setdefault(name, []).append(value)
        return {name: found[0] for name, found in values.items() if len(found) == 1}

    def bound_before(self, name: str) -> frozenset[str]:
        """
        :param name: A name the class body assigns once.
        :return: The names the body binds before assigning it, which its value reads
            from the body rather than from the module.
        """
        bound: set[str] = set()
        for statement in self.definition.body:
            if assigned(statement)[0] == name:
                break
            bound |= PythonSource.names_defined_by(statement)
        return frozenset(bound)

    def resolved_value(self, name: str, renames: RenameMap) -> str | None:
        """
        :param name: A name the class body assigns once.
        :param renames: Renames of the dotted paths it reads.
        :return: The structure of its value with every name and chain of attributes it
            reads written as the renamed dotted path of what it refers to, ``None``
            when one is not proven or the value may depend on where it is defined.
        """
        value = self.assignments[name]
        if any(isinstance(node, UNRESOLVED_EXPRESSIONS) for node in ast.walk(value)):
            return None
        writer = ReferenceWriter(self, self.bound_before(name), renames)
        structure = ast.dump(writer.visit(copy.deepcopy(value)))
        if writer.unresolved or ORDER_DEPENDENT_VALUE in writer.paths:
            return None
        return structure

    def body_referent(
        self, expression: ast.expr, siblings: frozenset[str]
    ) -> Referent | None:
        """
        :param expression: A name or a chain of attributes the class body reads.
        :param siblings: The names the body has bound by then.
        :return: What it refers to, one of *siblings* being the class's own attribute.
        """
        if isinstance(expression, ast.Attribute):
            return self.resolver.attribute_referent(
                self.body_referent(expression.value, siblings), expression.attr
            )
        if isinstance(expression, ast.Name) and expression.id in siblings:
            return ClassAttribute(self.member, expression.id)
        names = self.resolver.names_of(self.member.module)
        if names is None:
            return None
        return self.resolver.module_expression_referent(names, expression)


@dataclass
class ReferenceWriter(ast.NodeTransformer):
    """
    Writes every name and chain of attributes a class body reads as one name, the dotted
    path of what it refers to.
    """

    owner: ClassVersion
    """
    The class whose body is read.
    """

    siblings: frozenset[str]
    """
    The names its body has bound before the value read.
    """

    renames: RenameMap
    """
    Renames of the dotted paths written.
    """

    unresolved: bool = False
    """
    Whether a read's referent was not proven.
    """

    paths: set[str] = field(default_factory=set)
    """
    Every dotted path written so far.
    """

    def visit_Name(self, node: ast.Name) -> ast.Name:
        """
        :param node: A name read.
        :return: The name of what it refers to.
        """
        return self.written(node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        """
        :param node: An attribute read.
        :return: The name of what it refers to when it is read from a chain of names,
            the attribute of the value it is read from written otherwise.
        """
        chain: ast.expr = node
        while isinstance(chain, ast.Attribute):
            chain = chain.value
        if isinstance(chain, ast.Name):
            return self.written(node)
        return self.generic_visit(node)

    def written(self, node: ast.Name | ast.Attribute) -> ast.Name:
        """
        :param node: A name or chain of names read.
        :return: The name of the renamed dotted path of what it refers to.
        """
        path = dotted_path(self.owner.body_referent(node, self.siblings))
        if path is None:
            self.unresolved = True
            return ast.Name(id="", ctx=ast.Load())
        renamed = self.renames.renamed_identifier(path)
        self.paths.add(renamed)
        return ast.Name(id=renamed, ctx=ast.Load())


@dataclass(frozen=True)
class ClassBehaviour:
    """
    What a class gives each of its members beyond the member's own value: the methods
    and attributes it and its ancestors in the commit define, the nearest one first, the
    decorators and keywords of each, and the classes outside the commit it inherits
    from.
    """

    attributes: tuple[tuple[str, str], ...]
    """
    The structure of each method or attribute by its name, the class's own assignments,
    its members, left out.
    """

    decorations: frozenset[str]
    """
    The structure of the decorators and keywords of the class and its ancestors.
    """

    outside_bases: frozenset[str]
    """
    The dotted paths of the classes outside the commit it inherits from.
    """

    @classmethod
    def from_class(cls, version: ClassVersion) -> ClassBehaviour | None:
        """
        :param version: A class.
        :return: Its behaviour, ``None`` when an ancestor is not proven to be a class
            of the commit or of the standard library, or its decorators and keywords
            are not all of the standard library.
        """
        resolver = version.resolver
        attributes: dict[str, str] = {}
        decorations: set[str] = set()
        outside: set[str] = set()
        pending = [version.member]
        visited = {version.member}
        while pending:
            member = pending.pop(0)
            definition = resolver.class_definition(member)
            if definition is None or not resolver.is_plain_class(member):
                return None
            decorations |= {
                ast.dump(part)
                for part in (*definition.decorator_list, *definition.keywords)
            }
            for statement in definition.body:
                for name, structure in cls.statement_attributes(
                    statement, member == version.member
                ):
                    attributes.setdefault(name, structure)
            for base in resolver.base_referents(member):
                if isinstance(base, StandardLibraryMember):
                    outside.add(
                        f"{base.module}{DOTTED_NAME_SEPARATOR}{base.member_name}"
                    )
                elif not isinstance(base, ModuleMember):
                    return None
                elif base not in visited:
                    visited.add(base)
                    pending.append(base)
        return cls(
            tuple(sorted(attributes.items())),
            frozenset(decorations),
            frozenset(outside),
        )

    def is_kept_by(
        self, successor: ClassBehaviour, reads: AttributeReadSearch, owner: ModuleMember
    ) -> bool:
        """
        :param successor: The behaviour of the class the members move into.
        :param reads: Where the head commit reads attributes.
        :param owner: That class.
        :return: Whether it gives every moved member what this behaviour gave: the
            same decorations and classes outside the commit, no attribute this one
            lacks, every attribute it still gives unchanged, and each it no longer
            gives read from none of its members.
        """
        if (self.decorations, self.outside_bases) != (
            successor.decorations,
            successor.outside_bases,
        ):
            return False
        given = dict(successor.attributes)
        if not given.keys() <= dict(self.attributes).keys():
            return False
        return all(
            given[name] == structure
            if name in given
            else reads.is_read_only_outside(name, owner)
            for name, structure in self.attributes
        )

    @staticmethod
    def statement_attributes(
        statement: ast.stmt, is_own: bool
    ) -> Iterator[tuple[str, str]]:
        """
        :param statement: A statement of a class body.
        :param is_own: Whether the body is that of the class whose members are compared,
            whose own assignments are its members rather than what it gives them.
        :return: The name and structure of each attribute it defines.
        """
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            yield statement.name, ast.dump(statement)
            return
        name, _ = assigned(statement)
        if name is not None and not is_own:
            yield name, ast.dump(statement)


@dataclass
class AttributeReadSearch:
    """
    Finds where one commit reads an attribute by its name, each name searched once.
    """

    resolver: MemberResolver
    """
    What the commit's names refer to.
    """

    readers: dict[str, frozenset[Referent] | None] = field(default_factory=dict)
    """
    What each name searched so far is read from, ``None`` when a read of it is not
    proven.
    """

    def is_read_only_outside(self, name: str, owner: ModuleMember) -> bool:
        """
        :param name: An attribute's name.
        :param owner: A class of the commit.
        :return: Whether every use of the name in the commit is a read from something
            proven to be neither the class nor one of its attributes.
        """
        readers = self.read_from(name)
        return readers is not None and not any(
            reader == owner
            or (isinstance(reader, ClassAttribute) and reader.owner == owner)
            for reader in readers
        )

    def read_from(self, name: str) -> frozenset[Referent] | None:
        """
        :param name: An attribute's name.
        :return: What the commit reads it from, ``None`` when it uses the name in any
            other way or a reader is not proven.
        """
        if name not in self.readers:
            modules = self.resolver.modules
            found: set[Referent] = set()
            for key in modules.files_naming(name):
                path = PurePosixPath(key.partition(FILE_KEY_SEPARATOR)[2])
                if path.suffix != MODULE_SUFFIX:
                    self.readers[name] = None
                    break
                readers = self.file_readers(
                    ModuleNames.from_text(
                        modules.module_path(path),
                        modules.texts_of((key,))[key],
                        path.name == PACKAGE_INITIALIZER,
                    ),
                    name,
                )
                if readers is None:
                    self.readers[name] = None
                    break
                found |= readers
            else:
                self.readers[name] = frozenset(found)
        return self.readers[name]

    def file_readers(self, names: ModuleNames, name: str) -> set[Referent] | None:
        """
        :param names: A module of the commit.
        :param name: An attribute's name.
        :return: What the module reads the attribute from, ``None`` when it uses the
            name otherwise or a reader is not proven.
        """
        if not names.source.parses:
            return None
        found: set[Referent] = set()
        for node in ast.walk(names.source.tree):
            if isinstance(node, ast.Attribute) and node.attr == name:
                reader = self.resolver.module_expression_referent(names, node.value)
                if not isinstance(node.ctx, ast.Load) or reader is None:
                    return None
                found.add(reader)
            elif (
                (isinstance(node, ast.Name) and node.id == name)
                or (isinstance(node, ast.Constant) and node.value == name)
                or (isinstance(node, ast.keyword) and node.arg == name)
            ):
                return None
        return found


# %% the classes a pull request changes


@dataclass(frozen=True)
class ClassChange:
    """
    A module's top-level class in the base and the head commit of a pull request, the
    base version absent where the base commit does not define it.
    """

    base: ClassVersion | None
    """
    The class the base commit defines.
    """

    head: ClassVersion
    """
    The class the head commit defines.
    """

    @property
    def lost(self) -> frozenset[str]:
        """
        The names the base version's body assigns and the head version's no longer does.
        """
        if self.base is None:
            return frozenset()
        return frozenset(self.base.assignments) - frozenset(self.head.assignments)

    @property
    def gained(self) -> frozenset[str]:
        """
        The names the head version's body assigns and the base version's did not.
        """
        base = frozenset() if self.base is None else frozenset(self.base.assignments)
        return frozenset(self.head.assignments) - base

    def behaves_alike(
        self, name: str, destination: ClassChange, moves: RenameMap
    ) -> bool:
        """
        :param name: An attribute this class loses.
        :param destination: A class gaining an attribute of that name.
        :param moves: The pull request's module, definition and attribute moves.
        :return: Whether reading it from the destination gives what reading it from
            this class gave: the same value, no other member of the destination with
            that value, and the same behaviour.
        """
        head_value = destination.head.resolved_value(name, RenameMap())
        if head_value is None or head_value != self.base.resolved_value(name, moves):
            return False
        if any(
            destination.head.resolved_value(other, RenameMap()) == head_value
            for other in destination.head.assignments
            if other != name
        ):
            return False
        behaviour = ClassBehaviour.from_class(self.base)
        successor = ClassBehaviour.from_class(destination.head)
        return (
            behaviour is not None
            and successor is not None
            and behaviour.is_kept_by(
                successor,
                AttributeReadSearch(destination.head.resolver),
                destination.head.member,
            )
        )

    @staticmethod
    def of_file(
        change: FileVersions, base: MemberResolver, head: MemberResolver
    ) -> Iterator[ClassChange]:
        """
        :param change: A Python file a pull request changes, each version parsable.
        :param base: What the base commit's names refer to.
        :param head: What the head commit's names refer to.
        :return: Each top-level class its head version defines that each commit proves
            to be one.
        """
        head_module = head.modules.module_path(change.path)
        base_classes: frozenset[str] = frozenset()
        base_module = ""
        if change.base_text is not None:
            base_module = base.modules.module_path(change.previous_path or change.path)
            base_classes = ClassChange.top_level_class_names(change.base_text)
        for name in sorted(ClassChange.top_level_class_names(change.head_text)):
            head_version = ClassVersion.from_commit(
                ModuleMember(head_module, name), head
            )
            if head_version is None:
                continue
            base_version = None
            if name in base_classes:
                base_version = ClassVersion.from_commit(
                    ModuleMember(base_module, name), base
                )
            yield ClassChange(base_version, head_version)

    @staticmethod
    def top_level_class_names(text: str) -> frozenset[str]:
        """
        :param text: A parsable Python module.
        :return: The names of the classes its top level defines.
        """
        return frozenset(
            statement.name
            for statement in PythonSource.from_text(text).tree.body
            if isinstance(statement, ast.ClassDef)
        )


# %% detection


@dataclass(frozen=True)
class AttributeMoveDetection(RenameSource):
    """
    Detects a class attribute that leaves a class the head commit keeps and that exactly
    one other class gains under the same name, as a rename of its dotted path, when
    reading it from the new class gives what reading it from the old one gave.
    """

    @classproperty
    def label(cls) -> str:
        return "attribute move"

    def decisions(self, changes: PullRequestChanges) -> RenameDecisions:
        base = MemberResolver(CommitModules(changes.commits.base_tree))
        head = MemberResolver(CommitModules(changes.commits.head_tree))
        losing: dict[str, list[ClassChange]] = {}
        gaining: dict[str, list[ClassChange]] = {}
        for change in changes.files:
            if (
                change.path.suffix != MODULE_SUFFIX
                or change.head_text is None
                or not PythonSource.every_version_parses(change)
            ):
                continue
            for class_change in ClassChange.of_file(change, base, head):
                for name in class_change.lost:
                    losing.setdefault(name, []).append(class_change)
                for name in class_change.gained:
                    gaining.setdefault(name, []).append(class_change)
        pairs = {
            name: [(old, new) for old in losers for new in gaining.get(name, [])]
            for name, losers in sorted(losing.items())
        }
        moves = RenameMap.from_decisions(
            [
                ModuleMoveDetection().decisions(changes),
                DefinitionMoveDetection().decisions(changes),
                RenameDecisions(
                    tuple(
                        self.move(name, *candidates[0])
                        for name, candidates in pairs.items()
                        if len(candidates) == 1
                    )
                ),
            ]
        )
        found = []
        for name, candidates in pairs.items():
            alike = [
                (old, new)
                for old, new in candidates
                if old.behaves_alike(name, new, moves)
            ]
            if len(alike) == 1:
                found.append(self.move(name, *alike[0]))
        return RenameDecisions(tuple(found))

    def move(self, name: str, old: ClassChange, new: ClassChange) -> AttributeMove:
        """
        :param name: An attribute's name.
        :param old: The class it leaves.
        :param new: The class it moves into.
        :return: The rename of its dotted path.
        """
        owner = old.base.member
        new_owner = new.head.member
        return AttributeMove(
            f"{owner.dotted_path}{DOTTED_NAME_SEPARATOR}{name}",
            f"{new_owner.dotted_path}{DOTTED_NAME_SEPARATOR}{name}",
            self,
            attribute=ClassAttribute(owner, name),
            new_owner=new_owner,
        )

"""
Comparing two syntax trees node by node, where pluggable rules allow particular
differences and record each as a finding that is proved harmless afterwards.
"""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property

from basstler.class_property import classproperty
from basstler.review_triage.calls import CallScope
from basstler.review_triage.comparison import ChangeKind, ReviewReason
from basstler.review_triage.definitions import DefinitionIndex, FunctionDefinition
from basstler.review_triage.member_renames import MemberRenamer
from basstler.review_triage.name_scopes import SCOPED_FIELDS, NameScope
from basstler.review_triage.python_source import ImportBindings, PythonSource
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.signatures import SignatureReader

# %% what a finding is proved against


@dataclass(frozen=True)
class CommitReaders:
    """
    Read the signatures of the commits a pull request compares.
    """

    base: SignatureReader
    """
    Reads the base commit's signatures.
    """

    head: SignatureReader
    """
    Reads the head commit's signatures.
    """

    member_renamer: MemberRenamer | None = None
    """
    Renames the base commit's proven occurrences of the module members the pull request
    renames; ``None`` when it renames none.
    """

    def renamed_base_definition(
        self, definition: FunctionDefinition
    ) -> FunctionDefinition:
        """
        :param definition: A function or method :attr:`base` read.
        :return: It as :meth:`MemberRenamer.renamed_definition` reads it, itself when
            the pull request renames no module member.
        """
        if self.member_renamer is None:
            return definition
        return self.member_renamer.renamed_definition(definition, self.base.definitions)


# %% findings


class Finding(ABC):
    """
    One allowed difference between the trees, harmless only once :meth:`unproven_reason`
    finds nothing.
    """

    @classproperty
    @abstractmethod
    def kind(cls) -> ChangeKind:
        """
        The kind of change a report lists this difference under.
        """

    @abstractmethod
    def unproven_reason(
        self, readers: CommitReaders, renames: RenameMap
    ) -> ReviewReason | None:
        """
        :param readers: Read the signatures of both commits.
        :param renames: The renames the pull request makes throughout.
        :return: Why the difference may change what the code does, ``None`` when it
            cannot.
        """

    def looked_up_names(self, renames: RenameMap) -> frozenset[str]:
        """
        :param renames: The renames the pull request makes throughout.
        :return: The names whose definitions :meth:`unproven_reason` looks up, to find every
            finding's together in one search.
        """
        return frozenset()


# %% rules


@dataclass(frozen=True)
class ComparedNodeTypes:
    """
    The type of a node of the base tree and that of the node at its place in the head
    tree.
    """

    base: type[ast.AST]
    """
    The type of the base tree's node.
    """

    head: type[ast.AST]
    """
    The type of the head tree's node.
    """

    @classmethod
    def alike(cls, *node_types: type[ast.AST]) -> tuple[ComparedNodeTypes, ...]:
        """
        :param node_types: Types of nodes.
        :return: Each type compared with a node of the same type.
        """
        return tuple(cls(node_type, node_type) for node_type in node_types)


class DifferenceRule(ABC):
    """
    Compares the nodes of some types, allowing a particular difference between them.
    """

    @classproperty
    @abstractmethod
    def compared_types(cls) -> tuple[ComparedNodeTypes, ...]:
        """
        The types of the pairs of nodes this rule compares.
        """

    @abstractmethod
    def matches(self, base: ast.AST, head: ast.AST, matcher: TreeMatcher) -> bool:
        """
        :param base: A node of the base tree, of a type of :attr:`compared_types`.
        :param head: The node at the same place in the head tree, of the type compared
            with it.
        :param matcher: The comparison in progress, for the nodes' children and to
            record findings.
        :return: Whether the two are equal but for differences this rule allows.
        """


# %% the comparison


@dataclass
class TreeMatcher:
    """
    One comparison of a base tree with a head tree, and the findings it records.
    """

    rules: tuple[DifferenceRule, ...]
    """
    The rules allowing differences, the first comparing a pair of node types deciding
    it.
    """

    head_imports: ImportBindings
    """
    The names the head version's imports bind.
    """

    findings: list[Finding] = field(default_factory=list)
    """
    Every allowed difference found so far.
    """

    mismatched_nodes: list[ast.stmt | ast.expr] = field(default_factory=list)
    """
    The head nodes found not to match, innermost first, left out once a caller matches
    them another way.
    """

    enclosing_classes: list[str] = field(default_factory=list)
    """
    The names of the classes whose bodies are being compared, innermost last.
    """

    parameter_types: list[dict[str, str]] = field(default_factory=list)
    """
    For each function whose body is being compared, innermost last, the class each
    parameter it never assigns to is annotated with.
    """

    name_scopes: list[NameScope] = field(default_factory=list)
    """
    The scopes whose code is being compared, the module's first and the innermost last.
    """

    imports: NameScope = field(default_factory=NameScope)
    """
    The names the imports of the base version bind, wherever they are.
    """

    file_definitions: DefinitionIndex = field(default_factory=DefinitionIndex)
    """
    The definitions of the base version of the file being compared.
    """

    module: PythonSource | None = None
    """
    The base version of the file being compared, ``None`` when unknown.
    """

    @cached_property
    def rule_by_types(self) -> dict[ComparedNodeTypes, DifferenceRule]:
        """
        The rule comparing each pair of node types some rule compares.
        """
        rules: dict[ComparedNodeTypes, DifferenceRule] = {}
        for rule in reversed(self.rules):
            rules |= dict.fromkeys(rule.compared_types, rule)
        return rules

    @property
    def scope(self) -> CallScope:
        """
        What the code around the nodes being compared tells about the names they use.
        """
        return CallScope(
            enclosing_class=(
                self.enclosing_classes[-1] if self.enclosing_classes else None
            ),
            parameter_types=self.parameter_types[-1] if self.parameter_types else {},
            name_scopes=tuple(self.name_scopes),
            imports=self.imports,
            file_definitions=self.file_definitions,
            module=self.module,
        )

    def matches(self, base: object, head: object) -> bool:
        """
        :param base: A node of the base tree, a list of them or one of their values.
        :param head: What is at the same place in the head tree.
        :return: Whether the two are equal but for differences the rules allow.
        """
        if isinstance(base, list):
            if not isinstance(head, list):
                return False
            if not all(map(self.matches, base, head)):
                return False
            if len(base) < len(head) and isinstance(head[len(base)], ast.stmt):
                self.mismatched_nodes.append(head[len(base)])
            return len(base) == len(head)
        if not isinstance(base, ast.AST):
            return base == head
        rule = self.rule_by_types.get(ComparedNodeTypes(type(base), type(head)))
        if rule is not None:
            matched = rule.matches(base, head, self)
        else:
            matched = type(base) is type(head) and self.matches_fields(base, head)
        if not matched and isinstance(head, (ast.stmt, ast.expr)):
            self.mismatched_nodes.append(head)
        return matched

    def matches_fields(
        self, base: ast.AST, head: ast.AST, skipped: frozenset[str] = frozenset()
    ) -> bool:
        """
        :param base: A node of the base tree.
        :param head: A node of the same type at the same place in the head tree.
        :param skipped: The fields the caller compares itself.
        :return: Whether every other field matches.
        """
        scoped = SCOPED_FIELDS.get(type(base), frozenset())
        for (field_name, base_value), (_, head_value) in zip(
            ast.iter_fields(base), ast.iter_fields(head), strict=True
        ):
            if field_name in skipped:
                continue
            if field_name in scoped:
                self.name_scopes.append(NameScope.opened_by(base))
            matched = self.matches(base_value, head_value)
            if field_name in scoped:
                self.name_scopes.pop()
            if not matched:
                return False
        return True

    def attempt(self, base: object, head: object) -> bool:
        """
        :meth:`matches`, keeping the findings and mismatches it records only when the
        two match, so that a caller may try another way of matching them.
        """
        recorded = len(self.findings)
        mismatched = len(self.mismatched_nodes)
        if self.matches(base, head):
            return True
        del self.findings[recorded:]
        del self.mismatched_nodes[mismatched:]
        return False

    def record(self, finding: Finding) -> None:
        """
        :param finding: An allowed difference just found.
        """
        self.findings.append(finding)

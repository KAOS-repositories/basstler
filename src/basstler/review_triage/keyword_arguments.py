"""
Judging a Python change that passes positional arguments by keyword, makes parameters
keyword-only or adds identity decorators as mechanical, once every call is shown to
bind the same values to the same parameters as before.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum

from basstler.class_property import classproperty
from basstler.review_triage.calls import (
    CALLEE_RESOLUTIONS,
    CalleeResolution,
    CallTarget,
)
from basstler.review_triage.comparison import (
    ChangeKind,
    ChangeKinds,
    JudgmentContext,
    MechanicalChange,
    PythonComparison,
    ReviewReason,
)
from basstler.review_triage.definitions import (
    DataclassName,
    DefinitionIndex,
    SourceDefinitions,
)
from basstler.review_triage.name_scopes import NameScope
from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.signatures import DecoratorPolicy, SignatureReader
from basstler.review_triage.tree_matching import DifferenceRule, Finding, TreeMatcher

# %% what the change consists of


class KeywordChange(ChangeKind):
    """
    The kinds of change of calls, parameters and decorators this judgment finds.
    """

    KEYWORD_ARGUMENTS = "keyword arguments"
    """
    Positional arguments are passed by the names of the parameters they were bound to.
    """

    KEYWORD_ONLY = "keyword-only parameters"
    """
    Parameters or dataclass fields became keyword-only; a call left passing them
    positionally fails instead of binding differently.
    """

    IDENTITY_DECORATORS = "identity decorators"
    """
    Decorators that return what they decorate unchanged were added.
    """


# %% why a difference needs review


class UnprovenBinding(StrEnum):
    """
    Why a call passing arguments by keyword is not shown to bind them as before.
    """

    RECEIVER_CLASS_UNKNOWN = (
        "the receiver's class is not inferred, and the methods of this name bind the"
        " arguments differently"
    )
    """
    The method is found by name only, and its definitions disagree.
    """

    SEVERAL_DEFINITIONS = "the definitions of this name bind the arguments differently"
    """
    The function is found by name only, and its definitions disagree.
    """

    BINDS_DIFFERENTLY = "the callee binds the arguments to other parameters"
    """
    The keywords name other parameters than the arguments were bound to.
    """

    NO_DEFINITION = "no definition of the callee in the base commit takes the arguments"
    """
    The callee is defined outside the repository, or takes fewer arguments.
    """

    UNREADABLE_SIGNATURE = "a definition the call may reach has an unreadable signature"
    """
    A definition is decorated or built so its parameters cannot be read.
    """


@dataclass(frozen=True)
class UnprovenKeywordCall(ReviewReason):
    """
    A call passing arguments by keyword, not shown to bind them as before.
    """

    callee: str
    """
    The name the call refers to its callee by.
    """

    cause: UnprovenBinding
    """
    Why it is not shown.
    """

    @property
    def explanation(self) -> str:
        return f"`{self.callee}` - {self.cause}"


@dataclass(frozen=True)
class UnprovenDecorator(ReviewReason):
    """
    An added decorator not shown to return what it decorates.
    """

    decorator: str
    """
    The name the decorator is referred to by.
    """

    @property
    def explanation(self) -> str:
        return f"`@{self.decorator}` is not shown to return what it decorates"


# %% findings


@dataclass(frozen=True)
class KeywordConversion(Finding):
    """
    A call whose trailing positional arguments the head commit passes by keyword.
    """

    target: CallTarget
    """
    What the call reaches its callee through.
    """

    first_position: int
    """
    The position of the first argument now passed by keyword.
    """

    keywords: tuple[str, ...]
    """
    The keywords of the arguments from that position on, in order.
    """

    callee: str
    """
    The name the call refers to its callee by.
    """

    line: int
    """
    The line of the head version the call starts on.
    """

    calls_method: bool
    """
    Whether the callee is an attribute of a receiver.
    """

    @classproperty
    def kind(cls) -> ChangeKind:
        return KeywordChange.KEYWORD_ARGUMENTS

    def unproven_reason(
        self, reader: SignatureReader, renames: RenameMap
    ) -> UnprovenKeywordCall | None:
        """
        ``None`` when every definition the call may reach that takes its positional
        arguments binds each to the parameter of its keyword, and at least one takes
        them.
        """
        cause = self.unproven_binding(reader, renames)
        if cause is None:
            return None
        return UnprovenKeywordCall(self.line, self.callee, cause)

    def unproven_binding(
        self, reader: SignatureReader, renames: RenameMap
    ) -> UnprovenBinding | None:
        """
        :param reader: Reads the base commit's signatures.
        :param renames: The renames the pull request makes throughout.
        :return: Why the call is not shown to bind its arguments as before, ``None``
            when it is.
        """
        target = self.target.in_base(renames)
        signatures = target.reachable_signatures(reader)
        if None in signatures:
            return UnprovenBinding.UNREADABLE_SIGNATURE
        keywords = tuple(map(renames.original_identifier, self.keywords))
        taking = [
            signature
            for signature in signatures
            if signature.accepts(self.first_position + len(keywords))
        ]
        if not taking:
            return UnprovenBinding.NO_DEFINITION
        if all(signature.binds(self.first_position, keywords) for signature in taking):
            return None
        if not target.known_by_name_only(reader):
            return UnprovenBinding.BINDS_DIFFERENTLY
        if self.calls_method:
            return UnprovenBinding.RECEIVER_CLASS_UNKNOWN
        return UnprovenBinding.SEVERAL_DEFINITIONS

    def looked_up_names(self, renames: RenameMap) -> frozenset[str]:
        """
        :meth:`Finding.looked_up_names`: those of the call's target.
        """
        return self.target.in_base(renames).looked_up_names()


@dataclass(frozen=True)
class KeywordOnlyDefinition(Finding):
    """
    A definition whose trailing positional parameters, or whose dataclass fields,
    became keyword-only.
    """

    @classproperty
    def kind(cls) -> ChangeKind:
        return KeywordChange.KEYWORD_ONLY

    def unproven_reason(
        self, reader: SignatureReader, renames: RenameMap
    ) -> ReviewReason | None:
        """
        Always ``None``: a call still passing such a parameter positionally fails
        instead of binding it to another parameter.
        """
        return None


@dataclass(frozen=True)
class AddedDecorator(Finding):
    """
    A decorator, referred to by a plain name, added to a definition.
    """

    name: str
    """
    The name the decorator is referred to by.
    """

    line: int
    """
    The line of the head version the decorator is on.
    """

    @classproperty
    def kind(cls) -> ChangeKind:
        return KeywordChange.IDENTITY_DECORATORS

    def unproven_reason(
        self, reader: SignatureReader, renames: RenameMap
    ) -> UnprovenDecorator | None:
        """
        ``None`` when every definition of the decorator in the base commit returns what
        it decorates.
        """
        if reader.definitions.is_identity(renames.original_identifier(self.name)):
            return None
        return UnprovenDecorator(self.line, self.name)

    def looked_up_names(self, renames: RenameMap) -> frozenset[str]:
        """
        :meth:`Finding.looked_up_names`: the decorator's name.
        """
        return frozenset({renames.original_identifier(self.name)})


# %% rules


@dataclass(frozen=True)
class ArgumentsPassedByKeyword(DifferenceRule):
    """
    Allows a call to pass its trailing positional arguments by keyword, the argument
    expressions kept and evaluated in the same order.
    """

    resolutions: tuple[CalleeResolution, ...] = CALLEE_RESOLUTIONS
    """
    The ways a call may reach its callee, the first giving it a target deciding it.
    """

    @classproperty
    def node_types(cls) -> tuple[type[ast.AST], ...]:
        return (ast.Call,)

    def matches(self, base: ast.Call, head: ast.Call, matcher: TreeMatcher) -> bool:
        kept = len(head.args)
        moved = base.args[kept:]
        new_keywords = head.keywords[: len(moved)]
        if not (
            len(new_keywords) == len(moved)
            and matcher.matches(base.func, head.func)
            and matcher.matches(base.args[:kept], head.args)
            and matcher.matches(base.keywords, head.keywords[len(moved) :])
        ):
            return False
        if not moved:
            return True
        scope = matcher.scope
        target = next(
            (
                found
                for resolution in self.resolutions
                if (found := resolution.target(base.func, scope)) is not None
            ),
            None,
        )
        if (
            target is None
            or any(isinstance(argument, ast.Starred) for argument in base.args)
            or any(keyword.arg is None for keyword in new_keywords)
            or not matcher.matches(moved, [keyword.value for keyword in new_keywords])
        ):
            return False
        matcher.record(
            KeywordConversion(
                target,
                kept,
                tuple(keyword.arg for keyword in new_keywords),
                PythonSource.referenced_name(head.func) or "",
                head.lineno,
                isinstance(head.func, ast.Attribute),
            )
        )
        return True


@dataclass(frozen=True)
class ParametersMadeKeywordOnly(DifferenceRule):
    """
    Allows a definition to make its trailing positional parameters keyword-only,
    keeping their names, annotations and defaults.
    """

    @classproperty
    def node_types(cls) -> tuple[type[ast.AST], ...]:
        return (ast.arguments,)

    def matches(
        self, base: ast.arguments, head: ast.arguments, matcher: TreeMatcher
    ) -> bool:
        kept = len(head.args)
        moved = base.args[kept:]
        positional = [*base.posonlyargs, *base.args]
        defaults = [None] * (len(positional) - len(base.defaults)) + base.defaults
        split = len(base.posonlyargs) + kept
        if moved and base.vararg is not None:
            return False
        if not (
            matcher.matches(base.posonlyargs, head.posonlyargs)
            and matcher.matches(base.args[:kept], head.args)
            and matcher.matches([*moved, *base.kwonlyargs], head.kwonlyargs)
            and matcher.matches(base.vararg, head.vararg)
            and matcher.matches(base.kwarg, head.kwarg)
            and matcher.matches(
                [default for default in defaults[:split] if default is not None],
                head.defaults,
            )
            and matcher.matches(
                [*defaults[split:], *base.kw_defaults], head.kw_defaults
            )
        ):
            return False
        if moved:
            matcher.record(KeywordOnlyDefinition())
        return True


@dataclass(frozen=True)
class DefinitionDecorators(DifferenceRule):
    """
    Allows a definition to add decorators referred to by plain names, and a class's
    dataclass decorator to gain ``kw_only=True``.
    """

    @classproperty
    def node_types(cls) -> tuple[type[ast.AST], ...]:
        return (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def matches(
        self,
        base: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        head: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        matcher: TreeMatcher,
    ) -> bool:
        if isinstance(base, ast.ClassDef):
            matcher.enclosing_classes.append(base.name)
            fields_match = matcher.matches_fields(
                base, head, frozenset({"decorator_list"})
            )
            matcher.enclosing_classes.pop()
        else:
            matcher.parameter_types.append(PythonSource.annotated_parameters(base))
            fields_match = matcher.matches_fields(
                base, head, frozenset({"decorator_list"})
            )
            matcher.parameter_types.pop()
        return fields_match and self.matches_decorators(base, head, matcher)

    def matches_decorators(
        self,
        base: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        head: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        matcher: TreeMatcher,
    ) -> bool:
        """
        :param base: A definition in the base tree.
        :param head: The same definition in the head tree.
        :param matcher: The comparison in progress.
        :return: Whether the head keeps each of the base's decorators in order, but
            for allowed additions and the dataclass decorator gaining ``kw_only``.
        """
        remaining = list(base.decorator_list)
        for decorator in head.decorator_list:
            if remaining and matcher.attempt(remaining[0], decorator):
                remaining.pop(0)
            elif remaining and self.adds_keyword_only(remaining[0], decorator, matcher):
                remaining.pop(0)
                matcher.record(KeywordOnlyDefinition())
            elif isinstance(decorator, (ast.Name, ast.Attribute)):
                matcher.record(
                    AddedDecorator(
                        PythonSource.referenced_name(decorator), decorator.lineno
                    )
                )
            else:
                return False
        return not remaining

    @staticmethod
    def adds_keyword_only(base: ast.expr, head: ast.expr, matcher: TreeMatcher) -> bool:
        """
        :param base: A decorator in the base tree.
        :param head: The decorator in its place in the head tree.
        :param matcher: The comparison in progress.
        :return: Whether the head is the base's standard dataclass decorator with
            ``kw_only=True`` added to its options.
        """
        if not (
            isinstance(head, ast.Call)
            and not head.args
            and matcher.head_imports.refers_to(
                head.func, DataclassName.MODULE, DataclassName.DECORATOR
            )
        ):
            return False
        added = [
            keyword
            for keyword in head.keywords
            if keyword.arg == DataclassName.KEYWORD_ONLY
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
        ]
        kept = [keyword for keyword in head.keywords if keyword not in added]
        if len(added) != 1:
            return False
        if not isinstance(base, ast.Call):
            return not kept and matcher.attempt(base, head.func)
        return (
            not base.args
            and matcher.attempt(base.func, head.func)
            and matcher.attempt(base.keywords, kept)
        )


KEYWORD_RULES: tuple[DifferenceRule, ...] = (
    ArgumentsPassedByKeyword(),
    ParametersMadeKeywordOnly(),
    DefinitionDecorators(),
)
"""
The built-in rules of the keyword judgment.
"""


# %% the judgment


@dataclass(frozen=True)
class KeywordArgumentComparison(PythonComparison):
    """
    Compares Python files as :class:`PythonComparison` does, also allowing the
    differences its rules find, once each is proved against the base commit.
    """

    rules: tuple[DifferenceRule, ...] = KEYWORD_RULES
    """
    The differences allowed between the code of both versions.
    """

    decorators: DecoratorPolicy = DecoratorPolicy()
    """
    Which decorated definitions of the base commit are read as written.
    """

    def code_changes(
        self, base: PythonSource, head: PythonSource, context: JudgmentContext
    ) -> ChangeKinds | None:
        """
        :meth:`PythonComparison.code_changes`, also allowing the differences
        :attr:`rules` find once every one of them holds.
        """
        kinds = super().code_changes(base, head, context)
        if kinds is not None:
            return kinds
        base_tree = base.code_tree(context.renames)
        matcher = TreeMatcher(
            self.rules,
            head.import_bindings,
            imports=NameScope.from_imports(base.renamed_tree(context.renames)),
            file_definitions=DefinitionIndex(SourceDefinitions((base.text,))),
            module=base,
            revealed_receivers=context.revealed_receivers,
        )
        if not matcher.matches(base_tree, head.code_tree(RenameMap())):
            return None
        reader = SignatureReader(context.base_definitions, self.decorators)
        renames = context.renames
        reader.definitions.load(
            frozenset().union(
                *(finding.looked_up_names(renames) for finding in matcher.findings)
            )
        )
        reasons = [
            reason
            for finding in matcher.findings
            if (reason := finding.unproven_reason(reader, renames)) is not None
        ]
        if reasons:
            context.review_reasons.extend(reasons)
            return None
        found: set[ChangeKind] = {finding.kind for finding in matcher.findings}
        if base.code(renames) != base.code(RenameMap()):
            found.add(MechanicalChange.RENAME)
        return frozenset(found)

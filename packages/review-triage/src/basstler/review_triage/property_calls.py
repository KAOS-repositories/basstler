"""
Judging a property read turned into a call of a method without arguments as mechanical,
once every method the call may reach reproduces the property it replaces.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum

from basstler.class_property import classproperty
from basstler.review_triage.calls import (
    CalleeResolutions,
    CallTarget,
    ReachableDefinition,
)
from basstler.review_triage.comparison import ChangeKind, ReviewReason
from basstler.review_triage.definitions import FunctionDefinition
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.tree_matching import (
    CommitReaders,
    ComparedNodeTypes,
    DifferenceRule,
    Finding,
    TreeMatcher,
)

PLAIN_PROPERTY_DECORATORS: tuple[str, ...] = ("property",)
"""
The decorators of a plain read-only property.
"""

# %% what the change consists of


class PropertyCallChange(ChangeKind):
    """
    The kinds of change of property reads this judgment finds.
    """

    PROPERTIES_CALLED = "properties called as methods"
    """
    Reads of properties became calls of methods without arguments doing what they did.
    """


# %% why a difference needs review


class UnprovenReplacement(StrEnum):
    """
    Why a method call is not shown to do what the property read it replaces did.
    """

    NO_DEFINITION = "no definition of the property is found in the base commit"
    """
    The base commit defines nothing the read may reach.
    """

    UNREADABLE_DEFINITION = "a definition it may reach is not read"
    """
    A definition the read or the call may reach cannot be read.
    """

    NO_METHOD = "no method the call may run is found in the head commit"
    """
    The head commit defines nothing an instance may run for the call.
    """

    NOT_A_PROPERTY = "the attribute read was no plain property"
    """
    The read may reach something other than a read-only property.
    """

    DECORATED_METHOD = "the method called is decorated"
    """
    The call may reach a method whose decorators may change what calling it does.
    """

    NOT_REPRODUCED = "the method does not reproduce the property"
    """
    The call may reach a method whose code differs from that of the property it
    replaces.
    """

    RECEIVER_CLASS_UNKNOWN = (
        "the receiver's class is not inferred, and the methods of this name do not"
        " reproduce the properties"
    )
    """
    The receiver's class is unknown, and some method of the name differs from the
    property of its class.
    """


@dataclass(frozen=True)
class UnprovenPropertyCall(ReviewReason):
    """
    A method call replacing a property read, not shown to do what the read did.
    """

    method: str
    """
    The name of the method called.
    """

    cause: UnprovenReplacement
    """
    Why it is not shown.
    """

    unproven_definitions: tuple[str, ...]
    """
    The qualified names of the definitions the read or the call may reach that are
    not reproduced on the other side or cannot be read.
    """

    @property
    def explanation(self) -> str:
        if not self.unproven_definitions:
            return f"`{self.method}()` - {self.cause}"
        listed = ", ".join(f"`{name}`" for name in self.unproven_definitions)
        return f"`{self.method}()` - {self.cause}: {listed}"


# %% findings


@dataclass(frozen=True)
class PropertyCall(Finding):
    """
    A read of a property the head commit replaces by calling a method without
    arguments.
    """

    target: CallTarget
    """
    What the call reaches its method through, in the head commit's names.
    """

    method: str
    """
    The name of the method called.
    """

    line: int
    """
    The line of the head version the call starts on.
    """

    @classproperty
    def kind(cls) -> ChangeKind:
        return PropertyCallChange.PROPERTIES_CALLED

    def unproven_reason(
        self, readers: CommitReaders, renames: RenameMap
    ) -> UnprovenPropertyCall | None:
        """
        ``None`` when the read reaches only plain properties, the call only undecorated
        methods an instance may run, and each property's code, renamed, is that of one
        such method, each method reproducing one property.
        """
        base_target = self.target.in_base(renames)
        properties = base_target.reachable_definitions(readers.base)
        methods = [
            found
            for found in self.target.reachable_definitions(readers.head)
            if not isinstance(found.definition, FunctionDefinition)
            or readers.head.definitions.runs_on_instances(found.definition)
        ]
        unreadable = [
            found for found in [*properties, *methods] if found.definition is None
        ]
        if unreadable:
            return self.reason(UnprovenReplacement.UNREADABLE_DEFINITION, unreadable)
        if not properties:
            return self.reason(UnprovenReplacement.NO_DEFINITION, [])
        not_properties = [
            found
            for found in properties
            if not isinstance(found.definition, FunctionDefinition)
            or found.definition.decorators != PLAIN_PROPERTY_DECORATORS
        ]
        if not_properties:
            return self.reason(UnprovenReplacement.NOT_A_PROPERTY, not_properties)
        if not methods:
            return self.reason(UnprovenReplacement.NO_METHOD, [])
        decorated = [
            found
            for found in methods
            if not isinstance(found.definition, FunctionDefinition)
            or found.definition.decorators
        ]
        if decorated:
            return self.reason(UnprovenReplacement.DECORATED_METHOD, decorated)
        unreproduced = self.unreproduced(properties, methods, renames)
        if not unreproduced:
            return None
        if base_target.known_by_name_only(readers.base):
            return self.reason(UnprovenReplacement.RECEIVER_CLASS_UNKNOWN, unreproduced)
        return self.reason(UnprovenReplacement.NOT_REPRODUCED, unreproduced)

    @staticmethod
    def unreproduced(
        properties: list[ReachableDefinition],
        methods: list[ReachableDefinition],
        renames: RenameMap,
    ) -> list[ReachableDefinition]:
        """
        :param properties: The properties the base commit's read may reach.
        :param methods: The methods the head commit's call may reach.
        :param renames: The renames the pull request makes throughout.
        :return: The properties no method reproduces under its renamed name, or, when
            there are none, the methods reproducing no property.
        """
        renamed_properties = {
            (
                renames.renamed_identifier(found.qualified_name),
                found.definition.undecorated_code(renames),
            ): found
            for found in properties
        }
        method_codes = {
            (
                found.qualified_name,
                found.definition.undecorated_code(RenameMap()),
            ): found
            for found in methods
        }
        return [
            found
            for code, found in renamed_properties.items()
            if code not in method_codes
        ] or [
            found
            for code, found in method_codes.items()
            if code not in renamed_properties
        ]

    def reason(
        self, cause: UnprovenReplacement, unproven: list[ReachableDefinition]
    ) -> UnprovenPropertyCall:
        """
        :param cause: Why the call is not shown to do what the read did.
        :param unproven: The definitions it may reach that are not shown to.
        :return: The reason for review naming them.
        """
        return UnprovenPropertyCall(
            self.line,
            self.method,
            cause,
            tuple(sorted({found.qualified_name for found in unproven})),
        )

    def looked_up_names(self, renames: RenameMap) -> frozenset[str]:
        """
        :meth:`Finding.looked_up_names`: those of the read's target.
        """
        return self.target.in_base(renames).looked_up_names()


# %% rules


@dataclass(frozen=True)
class PropertyReadAsMethodCall(DifferenceRule):
    """
    Allows reading an attribute to become calling the method of the same name without
    arguments on the same receiver.
    """

    resolutions: CalleeResolutions = CalleeResolutions()
    """
    The ways the read may reach its definition.
    """

    @classproperty
    def compared_types(cls) -> tuple[ComparedNodeTypes, ...]:
        return (ComparedNodeTypes(ast.Attribute, ast.Call),)

    def matches(
        self, base: ast.Attribute, head: ast.Call, matcher: TreeMatcher
    ) -> bool:
        method = head.func
        if (
            not isinstance(method, ast.Attribute)
            or head.args
            or head.keywords
            or not isinstance(base.ctx, ast.Load)
            or base.attr != method.attr
            or not matcher.matches(base.value, method.value)
        ):
            return False
        target = self.resolutions.target(base, matcher.scope)
        if target is None:
            return False
        matcher.record(PropertyCall(target, method.attr, head.lineno))
        return True

"""
The fixes that remove what a checker reports, the behaviour each declares, and applying
them to a module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import libcst

from basstler.class_property import classproperty
from basstler.code_modification.actions import (
    Action,
    ActionPlan,
    AppliedAction,
    ImportInsertion,
    NodeReplacement,
    NodeReplacements,
)
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_file import PythonSourceFile
from basstler.code_modification.specification import Specification
from basstler.code_modification.syntax import CallSyntax
from basstler.code_rules.checker import CodeRuleChecker, CodeRuleViolation
from basstler.code_rules.commands import CodeRulesCommand
from basstler.code_rules.exceptions import FixDoesNotConvergeError

# %% behaviour


class BehaviourEffect(StrEnum):
    """
    Whether fixed code behaves as the code it replaces.
    """

    PRESERVED = "preserved"
    """
    The fixed code does what the code it replaces did.
    """

    CHANGED = "changed"
    """
    The fixed code does something else, which the declaration explains.
    """


@dataclass(frozen=True)
class BehaviourDeclaration:
    """
    How a fix changes what the code it fixes does.
    """

    effect: BehaviourEffect
    """
    Whether the behaviour changes.
    """

    explanation: str
    """
    What the fixed code does differently, or why it does the same.
    """


# %% fixes


class CodeFix[SpecificationType: Specification](ABC):
    """
    The one change that removes a place a checker specifies.
    """

    @classproperty
    @abstractmethod
    def behaviour(cls) -> BehaviourDeclaration:
        """
        How the fixed code behaves compared with the code it replaces.
        """

    @classproperty
    def required_import(cls) -> type | None:
        """
        The class the replacement needs imported in the module, if any.
        """
        return None

    @abstractmethod
    def replacement(self, specification: SpecificationType) -> libcst.CSTNode:
        """
        :param specification: A place breaking the fix's rule.
        :return: The node taking the place of the specification's node, which no
            longer breaks the rule.
        """


@dataclass(frozen=True)
class CallLackingKeywordArgument(Specification):
    """
    A call that has to pass one more keyword argument.
    """

    node: libcst.Call
    """
    The call.
    """

    superseded_argument: libcst.Arg | None = None
    """
    The argument of the call the keyword argument takes the place of, if any.
    """


class KeywordArgumentFix(CodeFix[CallLackingKeywordArgument], ABC):
    """
    Passes a call one keyword argument, in place of the argument it supersedes where
    the call has one.
    """

    @classproperty
    @abstractmethod
    def keyword(cls) -> str:
        """
        The keyword the argument is passed by.
        """

    @classproperty
    @abstractmethod
    def value(cls) -> libcst.BaseExpression:
        """
        The value passed.
        """

    def replacement(self, specification: CallLackingKeywordArgument) -> libcst.Call:
        call = CallSyntax(specification.node)
        argument = CallSyntax.keyword_argument(self.keyword, self.value)
        if specification.superseded_argument is None:
            return call.with_argument_appended(argument)
        return call.with_argument_replaced(specification.superseded_argument, argument)


class FixableChecker[SpecificationType: Specification](CodeRuleChecker, ABC):
    """
    A checker each place it reports specifies the change its fix makes there.
    """

    @classproperty
    @abstractmethod
    def fix(cls) -> CodeFix[SpecificationType]:
        """
        The fix removing each place the checker reports.
        """

    @classproperty
    @abstractmethod
    def violation_description(cls) -> str:
        """
        What is wrong with each place the checker reports, as one sentence fragment.
        """

    @abstractmethod
    def specifications_of_module(
        self, module: PositionedModule
    ) -> Iterator[SpecificationType]:
        """
        :param module: A module to check.
        :return: Every place in it that breaks the rule.
        """

    def checks(self, path: Path) -> bool:
        """
        :param path: A Python source file.
        :return: Whether the checker reports places in it.
        """
        return True

    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        if not self.checks(path):
            return
        module = PositionedModule(PythonSourceFile(path).parse())
        for specification in self.specifications_of_module(module):
            yield CodeRuleViolation(
                path,
                specification.location.start.line,
                specification.location.end.line,
                f"{self.violation_description}; `{CodeRulesCommand.FIX.invocation}` "
                "fixes it",
            )


# %% fixing a module


@dataclass(frozen=True)
class FixablePlace:
    """
    A place breaking a rule, and the fix that removes it.
    """

    fix: CodeFix
    """
    The fix of the checker that found the place.
    """

    specification: Specification
    """
    The place.
    """

    @property
    def action(self) -> NodeReplacement:
        """
        The action making the fix's change at the place.
        """
        return NodeReplacement(
            self.specification.location,
            self.specification.node,
            self.fix.replacement(self.specification),
        )


@dataclass(frozen=True)
class SourceFixer:
    """
    Applies the fixes of a set of checkers to a module until no checker reports
    anything.
    """

    checkers: tuple[FixableChecker, ...]
    """
    The checkers whose fixes are applied.
    """

    def fix_module(self, module: libcst.Module, path: Path) -> AppliedAction:
        """
        :param module: The module to fix, which is left as it is.
        :param path: The file *module* is the source of.
        :return: The module with every place the checkers report fixed, and the action
            restoring the module exactly.
        :raises FixDoesNotConvergeError: If a round of fixes leaves at least as many
            places breaking a rule as there were before it.
        """
        inverses: list[Action] = []
        imports: list[type] = []
        places = self.places(module, path)
        while places:
            imports.extend(
                place.fix.required_import
                for place in places
                if place.fix.required_import is not None
            )
            applied = self.round_of_fixes(places).apply(module)
            module = applied.module
            inverses.append(applied.inverse)
            remaining = self.places(module, path)
            if len(remaining) >= len(places):
                raise FixDoesNotConvergeError(
                    tuple(
                        place.specification.location.start.line for place in remaining
                    )
                )
            places = remaining
        for imported in dict.fromkeys(imports):
            applied = ImportInsertion(imported).apply(module)
            module = applied.module
            inverses.append(applied.inverse)
        return AppliedAction(module, ActionPlan(tuple(reversed(inverses))))

    def places(self, module: libcst.Module, path: Path) -> list[FixablePlace]:
        """
        :param path: The file *module* was parsed from.
        :return: Every place in *module* that one of :attr:`checkers` that checks *path*
            reports.
        """
        positioned = PositionedModule(module)
        return [
            FixablePlace(checker.fix, specification)
            for checker in self.checkers
            if checker.checks(path)
            for specification in checker.specifications_of_module(positioned)
        ]

    @staticmethod
    def round_of_fixes(places: list[FixablePlace]) -> NodeReplacements:
        """
        :param places: Places breaking a rule, some perhaps inside others.
        :return: The fixes of every place that overlaps no place before it, outermost
            first, made at once.
        """
        chosen: list[FixablePlace] = []
        for place in sorted(
            places,
            key=lambda place: (
                place.specification.location.start.line,
                place.specification.location.start.column,
                -place.specification.location.end.line,
                -place.specification.location.end.column,
            ),
        ):
            if not any(
                place.specification.overlaps(other.specification) for other in chosen
            ):
                chosen.append(place)
        return NodeReplacements(tuple(place.action for place in chosen))

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
    NodeReplacement,
)
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.specification import Specification
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

    @abstractmethod
    def replacement(self, specification: SpecificationType) -> libcst.CSTNode:
        """
        :param specification: A place breaking the fix's rule.
        :return: The node taking the place of the specification's node, which no
            longer breaks the rule.
        """


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
    def specifications(self, module: PositionedModule) -> Iterator[SpecificationType]:
        """
        :param module: A module to check.
        :return: Every place in it that breaks the rule.
        """

    def violations(self, path: Path) -> Iterator[CodeRuleViolation]:
        module = PositionedModule(libcst.parse_module(path.read_text(encoding="utf-8")))
        for specification in self.specifications(module):
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
    def action(self) -> Action:
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

    def fixed(self, module: libcst.Module) -> AppliedAction:
        """
        :param module: The module to fix, which is left as it is.
        :return: The module with every place the checkers report fixed, and the action
            restoring *module* exactly.
        :raises FixDoesNotConvergeError: If a round of fixes leaves at least as many
            places breaking a rule as there were before it.
        """
        inverses: list[Action] = []
        places = self.places(module)
        while places:
            applied = self.round_of_fixes(places).apply(module)
            module = applied.module
            inverses.append(applied.inverse)
            remaining = self.places(module)
            if len(remaining) >= len(places):
                raise FixDoesNotConvergeError(
                    tuple(
                        place.specification.location.start.line for place in remaining
                    )
                )
            places = remaining
        return AppliedAction(module, ActionPlan(tuple(reversed(inverses))))

    def places(self, module: libcst.Module) -> list[FixablePlace]:
        """
        :return: Every place in *module* that one of :attr:`checkers` reports.
        """
        positioned = PositionedModule(module)
        return [
            FixablePlace(checker.fix, specification)
            for checker in self.checkers
            for specification in checker.specifications(positioned)
        ]

    @staticmethod
    def round_of_fixes(places: list[FixablePlace]) -> ActionPlan:
        """
        :param places: Places breaking a rule, some perhaps inside others.
        :return: The fixes of every place that overlaps no place before it, outermost
            first, applied from the end of the module towards its start so that each
            leaves the location of the next unchanged.
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
        return ActionPlan(tuple(place.action for place in reversed(chosen)))

"""
Tests for :mod:`basstler.code_rules.fixes`: every rule's fix, run on its examples, and
fixing until nothing breaks a rule.
"""

from __future__ import annotations

from collections.abc import Iterator

import libcst
import pytest

from basstler.class_property import classproperty
from basstler.code_modification.positions import PositionedModule
from basstler.code_modification.source_file import EditablePythonSourceFile
from basstler.code_modification.specification import Specification
from basstler.code_rules import rules
from basstler.code_rules.exceptions import FixDoesNotConvergeError
from basstler.code_rules.fixes import (
    BehaviourDeclaration,
    BehaviourEffect,
    CodeFix,
    FixableChecker,
    SourceFixer,
)
from basstler.code_rules.rule_module import RuleModule
from basstler.code_rules.text_file_usage import TextFileChecker
from basstler.locations import PackageLocation

from basstler_testing.constants.paths import CodeModificationSnippet
from .fix_example import FixExample

FIXABLE_CHECKERS = RuleModule(rules).fixable_checkers
"""
Every checker of the repository's rules that has a fix.
"""

EXAMPLES = [
    example for checker in FIXABLE_CHECKERS for example in FixExample.all_of(checker)
]
"""
The examples of every fix.
"""


def fixed(example: FixExample) -> libcst.Module:
    """
    :return: The example's code breaking the rule, fixed.
    """
    return (
        SourceFixer((example.checker,))
        .fix_module(EditablePythonSourceFile(example.before))
        .result
    )


# %% every fix on its examples


@pytest.mark.parametrize(
    "checker", FIXABLE_CHECKERS, ids=lambda checker: type(checker).__name__
)
def test_every_fix_has_an_example(checker):
    """
    A fix is declared together with code it is shown to fix.
    """
    assert FixExample.all_of(checker) != []


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.identifier)
def test_a_fix_turns_each_example_into_its_fixed_code(example):
    """
    Fixing the code breaking the rule gives the fixed code, character for character.
    """
    assert fixed(example).code == EditablePythonSourceFile(example.after).read()


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.identifier)
def test_undoing_a_fix_restores_each_example_exactly(example):
    """
    The inverse of a fix turns the fixed code back into the code it fixed.
    """
    before = EditablePythonSourceFile(example.before)
    applied = SourceFixer((example.checker,)).fix_module(before)

    assert applied.inverse.apply(applied.result).result.code == before.read()


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.identifier)
def test_fixed_code_breaks_the_rule_no_longer(example):
    """
    The checker reports nothing in an example's fixed code.
    """
    assert list(example.checker.violations(example.after)) == []


# %% fixing that never ends


class UnchangingFix(CodeFix[Specification]):
    """
    A fix that puts each place's node back as it was.
    """

    @classproperty
    def behaviour(cls) -> BehaviourDeclaration:
        return BehaviourDeclaration(
            BehaviourEffect.PRESERVED, "The code is left as it is."
        )

    def replacement(self, specification: Specification) -> libcst.CSTNode:
        return specification.node


class PrintCallChecker(FixableChecker[Specification]):
    """
    Reports every call of :func:`print`, with a fix that leaves it in place.
    """

    @classproperty
    def fix(cls) -> CodeFix[Specification]:
        return UnchangingFix()

    @classproperty
    def violation_description(cls) -> str:
        return "calls print"

    def specifications_of_module(
        self, module: PositionedModule
    ) -> Iterator[Specification]:
        for node, location in module.positions.items():
            if isinstance(node, libcst.Call) and node.func.deep_equals(
                libcst.Name(print.__name__)
            ):
                yield Specification(location, node)


def test_a_fix_leaving_its_rule_broken_raises():
    """
    A round of fixes that removes no place stops with an error instead of repeating
    forever.
    """
    with pytest.raises(FixDoesNotConvergeError):
        SourceFixer((PrintCallChecker(),)).fix_module(
            EditablePythonSourceFile(CodeModificationSnippet.PRINT_CALL)
        )


# %% files a checker skips


def test_a_checker_that_skips_a_file_fixes_nothing_in_it():
    """
    The program that runs without ``basstler`` keeps the path methods it reads with.
    """
    source_file = EditablePythonSourceFile(PackageLocation.UPSTREAM_REVIEWS_FETCH)

    fixed = SourceFixer((TextFileChecker(),)).fix_module(source_file)

    assert fixed.result.code == source_file.read()

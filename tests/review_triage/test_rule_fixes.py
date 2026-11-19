"""
Tests for :mod:`basstler.review_triage.rule_fixes`: a change proven mechanical by
recomputing a code rule's fix on the base.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from basstler.code_rules import rules
from basstler.code_rules.rule import Section
from basstler.code_rules.rule_module import RuleModule
from basstler.git.commit_range import FileVersions
from basstler.review_triage.comparison import (
    FileNeedingReview,
    FileTriager,
    JudgmentContext,
    MechanicalChange,
    MechanicalFile,
)
from basstler.review_triage.rule_fixes import RuleFixChange, RuleFixComparison
from basstler.review_triage.triage import PullRequestTriager
from basstler.text_file import TextFile

from ..code_rules.fix_example import FixExample
from .samples import FileSample

FIXABLE_RULES = RuleModule(rules).fixable_rules
"""
Every rule of the repository whose checker has a fix.
"""

EXAMPLES = [
    example for rule in FIXABLE_RULES for example in FixExample.all_of(rule.checker)
]
"""
Every example of every rule's fix.
"""

UTF_8_RULE_FIX = RuleFixChange[
    rules.project.PortabilityRules.READ_AND_WRITE_TEXT_AS_UTF_8.name
]
"""
The change the UTF-8 rule's fix makes, which the samples below make.
"""


def rules_fixed_by(example: FixExample) -> frozenset[Section]:
    """
    :return: The rules the example's code breaking its rule breaks and its fixed code no
        longer does, as their checkers report them.
    """
    return frozenset(
        rule
        for rule in FIXABLE_RULES
        if any(rule.checker.violations(example.before))
        and not any(rule.checker.violations(example.after))
    )


def triaged(change: FileVersions) -> MechanicalFile | FileNeedingReview:
    """
    :return: The verdict of the rule fix comparison alone on *change*.
    """
    return FileTriager(JudgmentContext(), (RuleFixComparison(),)).triage(change)


def example_change(example: FixExample) -> FileVersions:
    """
    :return: The change from the example's code breaking the rule to its fixed code.
    """
    return FileVersions(
        PurePosixPath("sample.py"),
        base_text=TextFile(example.before).read(),
        head_text=TextFile(example.after).read(),
    )


# %% every rule's fix


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.identifier)
def test_each_example_of_a_fix_is_mechanical_as_the_fixes_it_makes(
    example: FixExample,
):
    """
    Recomputing the fixes of the rules the example stops breaking on its code reproduces
    its fixed code, so the change is those fixes and nothing else.
    """
    change = example_change(example)
    assert triaged(change) == MechanicalFile(
        change, frozenset(RuleFixChange[rule.name] for rule in rules_fixed_by(example))
    )


def test_the_default_triage_proves_a_rule_s_fix_mechanical():
    """
    The pull request triage judges Python files with the rule fixes recomputed.
    """
    change = FileSample.UTF_8_FIX_REFORMATTED.change()
    verdict = FileTriager(JudgmentContext(), PullRequestTriager().judgments).triage(
        change
    )
    assert verdict == MechanicalFile(
        change, frozenset({UTF_8_RULE_FIX, MechanicalChange.FORMATTING})
    )


def test_the_fixes_of_two_rules_in_one_file_are_mechanical():
    """
    A file carrying the UTF-8 fix and the directory removal fix, with the import the
    latter adds laid out as the formatter lays it out, is both fixes and nothing else.
    """
    tree_removal_fix = RuleFixChange[
        rules.project.PortabilityRules.REMOVE_TREES_THROUGH_DIRECTORY_TREE.name
    ]
    change = FileSample.UTF_8_AND_TREE_REMOVAL_FIXES.change()
    assert triaged(change) == MechanicalFile(
        change,
        frozenset({UTF_8_RULE_FIX, tree_removal_fix, MechanicalChange.FORMATTING}),
    )


# %% what else the head may differ by


def test_a_fix_reformatted_afterwards_is_mechanical():
    """
    The head may lay the fixed code out differently, as a formatter run after the fix
    does.
    """
    change = FileSample.UTF_8_FIX_REFORMATTED.change()
    assert triaged(change) == MechanicalFile(
        change, frozenset({UTF_8_RULE_FIX, MechanicalChange.FORMATTING})
    )


@pytest.mark.parametrize(
    "sample", [FileSample.UTF_8_FIX_AND_CODE_CHANGED, FileSample.UTF_8_FIX_PARTIAL]
)
def test_a_head_the_fix_does_not_reproduce_needs_review(sample: FileSample):
    """
    A head changing code beyond the fix, or fixing only some places of the rule, needs
    review.
    """
    change = sample.change()
    assert triaged(change) == FileNeedingReview(change)

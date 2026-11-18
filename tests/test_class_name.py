"""
Tests for :mod:`basstler.class_name`.
"""

from __future__ import annotations

from basstler.class_name import HyphenatedClassName

# %% hyphenating a class name


class PlanItemKickoffExample(HyphenatedClassName):
    """
    A class whose name has several words and a suffix.
    """


def test_the_words_of_a_class_name_are_hyphenated_in_lower_case():
    """
    Each capital starts a new word.
    """
    assert PlanItemKickoffExample.hyphenated_class_name() == "plan-item-kickoff-example"


def test_a_suffix_is_left_out_of_the_hyphenated_name():
    """
    The suffix named is dropped before the words are split.
    """
    assert (
        PlanItemKickoffExample.hyphenated_class_name("Example") == "plan-item-kickoff"
    )

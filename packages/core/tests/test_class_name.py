"""
Tests for :mod:`basstler.class_name`.
"""

from __future__ import annotations

import pytest

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


# %% where a word starts


@pytest.mark.parametrize(
    ("name", "has_word_start"),
    [
        ("PlanItem", True),
        ("planItem", True),
        ("Plan", False),
        ("plan", False),
        ("", False),
    ],
)
def test_a_word_starts_before_each_capital_but_the_first_character(
    name: str, has_word_start: bool
):
    """
    Each name is listed beside whether a word starts inside it.
    """
    assert (HyphenatedClassName.word_start.search(name) is not None) is has_word_start

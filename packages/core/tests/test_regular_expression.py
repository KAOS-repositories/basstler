"""
Tests for :mod:`basstler.regular_expression`: building a pattern from named parts.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from basstler.regular_expression import (
    Anchor,
    CharacterClass,
    CharacterRange,
    CharacterSet,
    RegularExpression,
    Wildcard,
)

# %% parts the tests build from


class ExampleWord(StrEnum):
    """
    Text that holds characters a pattern would otherwise read as syntax.
    """

    VERSION = "1.0"
    """
    A dot, which a pattern reads as any character.
    """

    OPTIONAL_MARK = "a?"
    """
    A question mark, which a pattern reads as making the part before it optional.
    """


class ExampleGroup(StrEnum):
    """
    The names the tests capture parts under.
    """

    NUMBER = "number"
    """
    A run of digits.
    """


# %% text in a pattern


def test_text_matches_only_itself():
    """
    Characters a pattern would read as syntax match as written.
    """
    pattern = RegularExpression.sequence(ExampleWord.VERSION).compiled()
    assert pattern.fullmatch(ExampleWord.VERSION) is not None
    assert pattern.fullmatch("1x0") is None


def test_a_literal_matches_only_its_text_and_takes_a_repeat():
    """
    A literal is a single piece of text that can be repeated or made optional.
    """
    pattern = RegularExpression.literal(ExampleWord.OPTIONAL_MARK).optional().compiled()

    assert [
        pattern.fullmatch(text) is not None
        for text in ("", ExampleWord.OPTIONAL_MARK, "a")
    ] == [True, True, False]


def test_a_sequence_matches_its_parts_one_after_another():
    """
    Text and parts follow each other in the order given.
    """
    pattern = RegularExpression.sequence(
        ExampleWord.OPTIONAL_MARK, CharacterClass.DIGIT
    ).compiled()
    assert pattern.fullmatch(f"{ExampleWord.OPTIONAL_MARK}7") is not None
    assert pattern.fullmatch("7") is None


def test_either_matches_any_one_of_its_alternatives_and_nothing_else():
    """
    Each alternative matches whole, and nothing between them does.
    """
    pattern = RegularExpression.either(
        ExampleWord.VERSION, ExampleWord.OPTIONAL_MARK
    ).compiled()
    assert [
        pattern.fullmatch(text) is not None
        for text in (ExampleWord.VERSION, ExampleWord.OPTIONAL_MARK, "1x0")
    ] == [True, True, False]


# %% repetition


def test_an_optional_part_matches_once_or_not_at_all():
    """
    A part made optional never repeats.
    """
    pattern = RegularExpression.sequence(ExampleWord.VERSION).optional().compiled()
    assert [
        pattern.fullmatch(text) is not None
        for text in ("", ExampleWord.VERSION, ExampleWord.VERSION * 2)
    ] == [True, True, False]


def test_zero_or_more_matches_any_number_of_repeats():
    """
    No repeat at all matches too.
    """
    pattern = CharacterClass.DIGIT.zero_or_more().compiled()
    assert [pattern.fullmatch(text) is not None for text in ("", "1", "123")] == [
        True,
        True,
        True,
    ]


def test_one_or_more_needs_at_least_one_repeat():
    """
    The empty text does not match.
    """
    pattern = CharacterClass.DIGIT.one_or_more().compiled()
    assert [pattern.fullmatch(text) is not None for text in ("", "1", "123")] == [
        False,
        True,
        True,
    ]


def test_a_bounded_repeat_matches_only_within_its_bounds():
    """
    Both bounds count as within.
    """
    pattern = CharacterClass.DIGIT.repeated(2, 3).compiled()
    assert [
        pattern.fullmatch(text) is not None for text in ("1", "12", "123", "1234")
    ] == [False, True, True, False]


def test_the_shortest_repeat_stops_at_the_first_text_that_follows():
    """
    The repeat ends at the earliest place the rest of the pattern matches.
    """
    pattern = RegularExpression.sequence(
        Wildcard.ANY_CHARACTER.zero_or_more(shortest=True).captured_as(
            ExampleGroup.NUMBER
        ),
        ExampleWord.VERSION,
    ).compiled()
    match = pattern.match(f"12{ExampleWord.VERSION}34{ExampleWord.VERSION}")
    assert match[ExampleGroup.NUMBER] == "12"


# %% captures and lookarounds


def test_a_captured_part_is_read_back_under_its_name():
    """
    The match is read with the group's own name.
    """
    pattern = RegularExpression.sequence(
        ExampleWord.VERSION,
        CharacterClass.DIGIT.one_or_more().captured_as(ExampleGroup.NUMBER),
    ).compiled()
    assert pattern.fullmatch(f"{ExampleWord.VERSION}42")[ExampleGroup.NUMBER] == "42"


def test_a_lookahead_needs_its_part_to_follow_without_consuming_it():
    """
    The matched text ends before the part looked ahead for.
    """
    pattern = RegularExpression.sequence(
        CharacterClass.DIGIT, RegularExpression.lookahead(ExampleWord.VERSION)
    ).compiled()
    assert pattern.match(f"7{ExampleWord.VERSION}").group() == "7"
    assert pattern.match("7x") is None


def test_a_negative_lookahead_refuses_the_part_that_follows():
    """
    The match fails where the refused part comes next.
    """
    pattern = RegularExpression.sequence(
        CharacterClass.DIGIT, RegularExpression.negative_lookahead(CharacterClass.DIGIT)
    ).compiled()
    assert [pattern.match(text) is not None for text in ("7x", "77")] == [True, False]


def test_a_lookbehind_needs_its_part_to_come_before():
    """
    The matched text starts after the part looked behind for.
    """
    pattern = RegularExpression.sequence(
        RegularExpression.lookbehind(ExampleWord.VERSION), CharacterClass.DIGIT
    ).compiled()
    assert pattern.search(f"{ExampleWord.VERSION}7").group() == "7"
    assert pattern.search("x7") is None


def test_a_negative_lookbehind_refuses_the_part_that_comes_before():
    """
    Only a digit with no digit before it is found.
    """
    pattern = RegularExpression.sequence(
        RegularExpression.negative_lookbehind(CharacterClass.DIGIT),
        CharacterClass.DIGIT,
    ).compiled()
    assert pattern.findall("x78") == ["7"]


def test_a_backreference_matches_the_text_its_group_captured():
    """
    The same text must recur, not just text of the same kind.
    """
    pattern = RegularExpression.sequence(
        CharacterClass.DIGIT.captured_as(ExampleGroup.NUMBER),
        ExampleWord.VERSION,
        RegularExpression.backreference(ExampleGroup.NUMBER),
    ).compiled()
    assert [
        pattern.fullmatch(f"7{ExampleWord.VERSION}{last}") is not None
        for last in ("7", "8")
    ] == [True, False]


def test_a_case_insensitive_part_matches_its_text_in_any_case():
    """
    Only the part made case-insensitive ignores case.
    """
    pattern = RegularExpression.sequence(
        RegularExpression.sequence(ExampleWord.OPTIONAL_MARK).case_insensitive(),
        CharacterRange.ASCII_LOWERCASE_LETTER,
    ).compiled()
    assert [
        pattern.fullmatch(text) is not None
        for text in (f"{ExampleWord.OPTIONAL_MARK.upper()}b", "a?B")
    ] == [True, False]


# %% character sets


def test_a_character_set_matches_one_character_of_its_members():
    """
    Characters with a meaning inside a set match as written.
    """
    pattern = CharacterSet.any_of(
        CharacterRange.ASCII_LOWERCASE_LETTER, "-]"
    ).compiled()
    assert [pattern.fullmatch(text) is not None for text in ("q", "-", "]", "Q")] == [
        True,
        True,
        True,
        False,
    ]


def test_a_complement_set_matches_one_character_outside_its_members():
    """
    A character class and text members are both refused.
    """
    pattern = CharacterSet.any_except(CharacterClass.WHITESPACE, "^\\").compiled()
    assert [pattern.fullmatch(text) is not None for text in ("a", " ", "^", "\\")] == [
        True,
        False,
        False,
        False,
    ]


def test_a_range_on_its_own_matches_one_character_within_it():
    """
    A range outside a set is a set of its own.
    """
    pattern = CharacterRange.ASCII_DIGIT.compiled()
    assert [pattern.fullmatch(text) is not None for text in ("5", "a")] == [True, False]


def test_any_character_includes_a_line_break_and_the_other_wildcard_does_not():
    """
    The two wildcards differ only on a line break.
    """
    assert [
        wildcard.compiled().fullmatch("\n") is not None
        for wildcard in (
            Wildcard.ANY_CHARACTER,
            Wildcard.ANY_CHARACTER_EXCEPT_LINE_BREAK,
        )
    ] == [True, False]


@pytest.mark.parametrize(
    ("letters_and_digits", "text", "matches"),
    [
        (CharacterRange.ASCII_LETTER, "a", True),
        (CharacterRange.ASCII_LETTER, "Q", True),
        (CharacterRange.ASCII_LETTER, "7", False),
        (CharacterRange.ASCII_LETTER, "_", False),
        (CharacterRange.ASCII_ALPHANUMERIC, "a", True),
        (CharacterRange.ASCII_ALPHANUMERIC, "Q", True),
        (CharacterRange.ASCII_ALPHANUMERIC, "7", True),
        (CharacterRange.ASCII_ALPHANUMERIC, "_", False),
    ],
)
def test_a_range_of_letters_or_of_letters_and_digits_matches_one_of_them(
    letters_and_digits: CharacterRange, text: str, matches: bool
):
    """
    Each input is listed beside whether the range matches it.
    """
    pattern = RegularExpression.sequence(letters_and_digits).compiled()

    assert (pattern.fullmatch(text) is not None) is matches


def test_a_range_of_letters_and_digits_joins_a_set_beside_other_characters():
    """
    A set lists the range together with characters of its own.
    """
    pattern = CharacterSet.any_of(CharacterRange.ASCII_ALPHANUMERIC, "_").compiled()

    assert [pattern.fullmatch(text) is not None for text in ("a", "7", "_", "-")] == [
        True,
        True,
        True,
        False,
    ]


# %% anchors


def test_a_line_anchor_matches_at_every_line_of_the_text():
    """
    Every compiled pattern treats each line as having a start and an end.
    """
    pattern = RegularExpression.sequence(
        Anchor.LINE_START, CharacterClass.DIGIT, Anchor.LINE_END
    ).compiled()
    assert pattern.findall("1\nx\n2") == ["1", "2"]


def test_a_text_anchor_matches_only_at_the_start_of_the_whole_text():
    """
    The second line does not count as the start of the text.
    """
    pattern = RegularExpression.sequence(
        Anchor.TEXT_START, CharacterClass.DIGIT
    ).compiled()
    assert pattern.findall("1\n2") == ["1"]


def test_a_word_boundary_separates_a_word_from_what_surrounds_it():
    """
    A word character before the text means no boundary.
    """
    pattern = RegularExpression.sequence(
        Anchor.WORD_BOUNDARY, ExampleWord.OPTIONAL_MARK
    ).compiled()
    assert [
        pattern.search(text) is not None
        for text in (f" {ExampleWord.OPTIONAL_MARK}", f"b{ExampleWord.OPTIONAL_MARK}")
    ] == [True, False]


# %% compiling


def test_a_pattern_compiled_for_bytes_matches_bytes():
    """
    The same pattern reads encoded text.
    """
    pattern = RegularExpression.sequence(ExampleWord.VERSION).compiled_for_bytes()
    assert pattern.fullmatch(ExampleWord.VERSION.encode()) is not None

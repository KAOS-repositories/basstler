"""
A class's own name, spelled the way a command line or a document spells it.
"""

from __future__ import annotations

from basstler.regular_expression import (
    Anchor,
    CharacterRange,
    RegularExpression,
)

# %% where words start

WORD_START = RegularExpression.sequence(
    RegularExpression.negative_lookbehind(Anchor.TEXT_START),
    RegularExpression.lookahead(CharacterRange.ASCII_UPPERCASE_LETTER),
).compiled()
"""
The position before each capital letter but the first character, where a word starts.
"""

WORD_SEPARATOR = "-"
"""
What joins the words of a hyphenated name.
"""

# %% hyphenating


class HyphenatedClassName:
    """
    Gives a class the hyphenated, lower-case form of its own name.
    """

    @classmethod
    def hyphenated_class_name(cls, suffix: str = "") -> str:
        """
        :param suffix: A trailing part of the class name to leave out.
        :return: The class name in lower case, words joined by hyphens.
        """
        words = cls.__name__.removesuffix(suffix)
        return WORD_START.sub(WORD_SEPARATOR, words).lower()

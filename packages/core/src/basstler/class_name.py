"""
A class's own name, spelled the way a command line or a document spells it.
"""

from __future__ import annotations

import re
from enum import StrEnum

from basstler.class_property import classproperty
from basstler.regular_expression import (
    Anchor,
    CharacterRange,
    RegularExpression,
)

# %% hyphenating


class NameSyntax(StrEnum):
    """
    The symbols a hyphenated name is spelled with.
    """

    WORD_SEPARATOR = "-"
    """
    Joins the words of a hyphenated name.
    """


class HyphenatedClassName:
    """
    Gives a class the hyphenated, lower-case form of its own name.
    """

    @classproperty
    def word_start(cls) -> re.Pattern[str]:
        """
        The position before each capital letter but the first character, where a word
        starts, as before the ``I`` of ``PlanItem``.
        """
        return RegularExpression.sequence(
            RegularExpression.negative_lookbehind(Anchor.TEXT_START),
            RegularExpression.lookahead(CharacterRange.ASCII_UPPERCASE_LETTER),
        ).compiled()

    @classmethod
    def hyphenated_class_name(cls, suffix: str = "") -> str:
        """
        :param suffix: A trailing part of the class name to leave out.
        :return: The class name in lower case, words joined by hyphens.
        """
        words = cls.__name__.removesuffix(suffix)
        return cls.word_start.sub(NameSyntax.WORD_SEPARATOR, words).lower()

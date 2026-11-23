"""
A class's own name, spelled the way a command line or a document spells it.
"""

from __future__ import annotations

import re

from basstler.class_property import classproperty
from basstler.regular_expression import (
    Anchor,
    CharacterRange,
    CharacterSet,
    RegularExpression,
)

# %% hyphenating


class ClassNameWords:
    """
    The words a class name is spelled in.
    """

    @classproperty
    def pattern(cls) -> re.Pattern[str]:
        """
        One word of a class name, an acronym counting as one word, as ``CI`` and
        ``Pipeline`` in ``CIPipeline``.
        """
        acronym = RegularExpression.sequence(
            CharacterRange.ASCII_UPPERCASE_LETTER.one_or_more(),
            RegularExpression.negative_lookahead(CharacterRange.ASCII_LOWERCASE_LETTER),
        )
        capitalized_word = RegularExpression.sequence(
            CharacterRange.ASCII_UPPERCASE_LETTER,
            CharacterSet.any_of(
                CharacterRange.ASCII_LOWERCASE_LETTER, CharacterRange.ASCII_DIGIT
            ).zero_or_more(),
        )
        return RegularExpression.either(acronym, capitalized_word).compiled()

    @classmethod
    def split(cls, name: str) -> list[str]:
        """
        :param name: A class name.
        :return: Its words, in order.
        """
        return cls.pattern.findall(name)


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
        return cls.word_start.sub("-", words).lower()

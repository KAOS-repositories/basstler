"""
Regular expressions built from named parts, so a pattern reads as a sentence of what
each part means instead of a run of symbols.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

# %% the parts a pattern is built from


class PatternPart:
    """
    A piece of a regular expression, whose ``str`` is its pattern text, and the ways to
    repeat, capture and compile it.
    """

    def optional(self) -> RegularExpression:
        """
        :return: This part, matched once or not at all.
        """
        return RegularExpression(f"{self.grouped}?")

    def zero_or_more(self, shortest: bool = False) -> RegularExpression:
        """
        :param shortest: Whether to match as few repeats as let the rest match.
        :return: This part, repeated any number of times.
        """
        return RegularExpression(f"{self.grouped}*{self.laziness(shortest)}")

    def one_or_more(self, shortest: bool = False) -> RegularExpression:
        """
        :param shortest: Whether to match as few repeats as let the rest match.
        :return: This part, repeated at least once.
        """
        return RegularExpression(f"{self.grouped}+{self.laziness(shortest)}")

    def repeated(self, minimum: int, maximum: int) -> RegularExpression:
        """
        :param minimum: The fewest repeats.
        :param maximum: The most repeats.
        :return: This part, repeated within those bounds.
        """
        return RegularExpression(f"{self.grouped}{{{minimum},{maximum}}}")

    def captured_as(self, group: str) -> RegularExpression:
        """
        :param group: The name the matched text is read back under.
        :return: This part, its matched text kept under that name.
        """
        return RegularExpression(f"(?P<{group}>{str(self)})")

    def case_insensitive(self) -> RegularExpression:
        """
        :return: This part, matching its letters in either case.
        """
        return RegularExpression(f"(?i:{str(self)})")

    def compiled(self) -> re.Pattern[str]:
        """
        :return: The pattern for text, where a line anchor matches at every line.
        """
        return re.compile(str(self), re.MULTILINE)

    def compiled_for_bytes(self) -> re.Pattern[bytes]:
        """
        :return: The pattern for bytes, where a line anchor matches at every line.
        """
        return re.compile(str(self).encode(), re.MULTILINE)

    def __format__(self, format_spec: str) -> str:
        """
        :raises TypeError: Always: a part inside an f-string would turn into text that
            matches its own pattern syntax. Pass it to
            :meth:`RegularExpression.sequence` beside the text instead.
        """
        raise TypeError(
            f"{type(self).__name__} cannot be formatted into text; pass it to "
            "RegularExpression.sequence beside the text it follows"
        )

    @property
    def grouped(self) -> str:
        """
        This part's pattern text, enclosed so a quantifier applies to all of it.
        """
        return f"(?:{str(self)})"

    @staticmethod
    def laziness(shortest: bool) -> str:
        """
        :param shortest: Whether a repeat matches as few times as it can.
        :return: What follows a quantifier to make it so.
        """
        return "?" if shortest else ""


class Anchor(PatternPart, StrEnum):
    """
    A position in the text, which matches no character.
    """

    LINE_START = "^"
    """
    The start of a line.
    """

    LINE_END = "$"
    """
    The end of a line.
    """

    TEXT_START = r"\A"
    """
    The start of the whole text.
    """

    WORD_BOUNDARY = r"\b"
    """
    Between a word character and a character, or an end of the text, that is not one.
    """


class CharacterClass(PatternPart, StrEnum):
    """
    A kind of character, matching one character of that kind, alone or in a set.
    """

    WHITESPACE = r"\s"
    """
    A space, tab or line break.
    """

    NON_WHITESPACE = r"\S"
    """
    Any character but whitespace.
    """

    DIGIT = r"\d"
    """
    A decimal digit of any script.
    """

    WORD_CHARACTER = r"\w"
    """
    A letter, digit or underscore of any script.
    """


class CharacterRange(PatternPart, StrEnum):
    """
    A run of consecutive characters, matching one character within it, alone or in a
    set.
    """

    ASCII_UPPERCASE_LETTER = "A-Z"
    """
    An English capital letter.
    """

    ASCII_LOWERCASE_LETTER = "a-z"
    """
    An English small letter.
    """

    ASCII_DIGIT = "0-9"
    """
    A digit from zero to nine.
    """

    ASCII_LETTER = "A-Za-z"
    """
    An English letter in either case.
    """

    ASCII_ALPHANUMERIC = "A-Za-z0-9"
    """
    An English letter in either case, or a digit.
    """

    def __str__(self) -> str:
        """
        :return: The range as a set of its own.
        """
        return f"[{self.value}]"


class Wildcard(PatternPart, StrEnum):
    """
    Any one character, of a breadth no character class names.
    """

    ANY_CHARACTER = r"[\s\S]"
    """
    Any one character, a line break included.
    """

    ANY_CHARACTER_EXCEPT_LINE_BREAK = "."
    """
    Any one character but a line break.
    """


type CharacterSetMember = CharacterClass | CharacterRange | str
"""
What a set lists: a kind of character, a run of characters, or the characters of a text.
"""


@dataclass(frozen=True)
class CharacterSet(PatternPart):
    """
    One character, chosen from the members it lists or from outside them.
    """

    members: tuple[CharacterSetMember, ...]
    """
    The characters listed.
    """

    is_complement: bool = False
    """
    Whether a character outside the members matches, instead of one of them.
    """

    @classmethod
    def any_of(cls, *members: CharacterSetMember) -> CharacterSet:
        """
        :param members: The characters to choose from.
        :return: The set matching one of them.
        """
        return cls(members)

    @classmethod
    def any_except(cls, *members: CharacterSetMember) -> CharacterSet:
        """
        :param members: The characters to refuse.
        :return: The set matching any other character.
        """
        return cls(members, is_complement=True)

    def __str__(self) -> str:
        """
        :return: The set as pattern text, with text members matching as written.
        """
        listed = "".join(
            member.value
            if isinstance(member, (CharacterClass, CharacterRange))
            else re.escape(member)
            for member in self.members
        )
        return f"[{'^' if self.is_complement else ''}{listed}]"


# %% patterns built from parts


type PatternPiece = PatternPart | str
"""
A part of a pattern, or a text that matches only itself.
"""


@dataclass(frozen=True)
class RegularExpression(PatternPart):
    """
    A pattern composed from other parts.
    """

    source: str
    """
    The pattern text.
    """

    @classmethod
    def sequence(cls, *pieces: PatternPiece) -> RegularExpression:
        """
        :param pieces: The parts to match, in order.
        :return: The pattern matching each part right after the one before.
        """
        return cls("".join(cls.source_of(piece) for piece in pieces))

    @classmethod
    def literal(cls, text: str) -> RegularExpression:
        """
        :param text: Text that matches only itself.
        :return: The part matching it, which can be repeated or made optional.
        """
        return cls(re.escape(text))

    @classmethod
    def either(cls, *alternatives: PatternPiece) -> RegularExpression:
        """
        :param alternatives: The parts that may match.
        :return: The pattern matching any one of them.
        """
        return cls(f"(?:{'|'.join(cls.source_of(piece) for piece in alternatives)})")

    @classmethod
    def lookahead(cls, piece: PatternPiece) -> RegularExpression:
        """
        :param piece: The part that has to come next.
        :return: The position it follows, matching no character.
        """
        return cls(f"(?={cls.source_of(piece)})")

    @classmethod
    def negative_lookahead(cls, piece: PatternPiece) -> RegularExpression:
        """
        :param piece: The part that must not come next.
        :return: A position it does not follow, matching no character.
        """
        return cls(f"(?!{cls.source_of(piece)})")

    @classmethod
    def lookbehind(cls, piece: PatternPiece) -> RegularExpression:
        """
        :param piece: The part that has to come before, of a fixed length.
        :return: The position right after it, matching no character.
        """
        return cls(f"(?<={cls.source_of(piece)})")

    @classmethod
    def negative_lookbehind(cls, piece: PatternPiece) -> RegularExpression:
        """
        :param piece: The part that must not come before, of a fixed length.
        :return: A position not right after it, matching no character.
        """
        return cls(f"(?<!{cls.source_of(piece)})")

    @classmethod
    def backreference(cls, group: str) -> RegularExpression:
        """
        :param group: The name of a part captured earlier in the pattern.
        :return: The pattern matching the text that part matched.
        """
        return cls(f"(?P={group})")

    @staticmethod
    def source_of(piece: PatternPiece) -> str:
        """
        :param piece: A part of a pattern, or a text.
        :return: The pattern text of the part, or of the text matching only itself.
        """
        if isinstance(piece, PatternPart):
            return str(piece)
        return re.escape(piece)

    def __str__(self) -> str:
        """
        :return: The pattern text.
        """
        return self.source

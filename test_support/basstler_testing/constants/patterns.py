"""
The patterns several tests read the plugin's documents with.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.bash import ShellToken
from basstler.github.constants import MarkdownSyntax
from basstler.regular_expression import (
    CharacterRange,
    CharacterSet,
    RegularExpression,
)

# %% what is read back


class DocumentGroup(StrEnum):
    """
    The parts of a document the shared patterns read back.
    """

    LINK_TARGET = "link_target"
    """
    What a Markdown link points at.
    """

    VARIABLE = "variable"
    """
    The name of a shell variable.
    """


# %% shell names

SHELL_NAME = RegularExpression.sequence(
    CharacterSet.any_of(
        CharacterRange.ASCII_UPPERCASE_LETTER,
        CharacterRange.ASCII_LOWERCASE_LETTER,
        "_",
    ),
    CharacterSet.any_of(
        CharacterRange.ASCII_UPPERCASE_LETTER,
        CharacterRange.ASCII_LOWERCASE_LETTER,
        CharacterRange.ASCII_DIGIT,
        "_",
    ).zero_or_more(),
)
"""
A name the shell gives a variable or a function.
"""

BRACED_SHELL_VARIABLE = RegularExpression.sequence(
    ShellToken.BRACED_PARAMETER_START, SHELL_NAME.captured_as(DocumentGroup.VARIABLE)
).compiled()
"""
The start of a ``${NAME}`` reference, capturing the variable's name.
"""

# %% Markdown links


def markdown_link_target(*refused: str) -> RegularExpression:
    """
    :param refused: Characters the target may not hold, beside the one closing it.
    :return: A Markdown link, capturing its target.
    """
    return RegularExpression.sequence(
        MarkdownSyntax.LINK_TARGET_START,
        CharacterSet.any_except(MarkdownSyntax.LINK_TARGET_END, *refused)
        .one_or_more()
        .captured_as(DocumentGroup.LINK_TARGET),
        MarkdownSyntax.LINK_TARGET_END,
    )

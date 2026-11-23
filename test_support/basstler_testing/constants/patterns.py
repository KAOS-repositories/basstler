"""
The patterns several tests read the plugin's documents with.
"""

from __future__ import annotations

import re
from enum import StrEnum

from basstler.bash import ShellToken
from basstler.class_property import classproperty
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


class ShellPattern:
    """
    The patterns that read shell names out of a document.
    """

    @classproperty
    def variable_name(cls) -> RegularExpression:
        """
        A name the shell gives a variable or a function, as ``BASSTLER_PLUGIN_ROOT``.
        """
        return RegularExpression.sequence(
            CharacterSet.any_of(CharacterRange.ASCII_LETTER, "_"),
            CharacterSet.any_of(CharacterRange.ASCII_ALPHANUMERIC, "_").zero_or_more(),
        )

    @classproperty
    def braced_variable(cls) -> re.Pattern[str]:
        """
        The start of a ``${NAME}`` reference, capturing the variable's name.
        """
        return RegularExpression.sequence(
            ShellToken.BRACED_PARAMETER_START,
            cls.variable_name.captured_as(DocumentGroup.VARIABLE),
        ).compiled()


# %% Markdown links


class MarkdownLinkPattern:
    """
    The patterns that read Markdown links out of a document.
    """

    @staticmethod
    def target(*refused: str) -> RegularExpression:
        """
        :param refused: Characters the target may not hold, beside the one closing it.
        :return: A Markdown link, capturing its target, as ``](docs/a.md)``.
        """
        return RegularExpression.sequence(
            MarkdownSyntax.LINK_TARGET_START,
            CharacterSet.any_except(MarkdownSyntax.LINK_TARGET_END, *refused)
            .one_or_more()
            .captured_as(DocumentGroup.LINK_TARGET),
            MarkdownSyntax.LINK_TARGET_END,
        )

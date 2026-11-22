"""
Tests that the setup skill names only rows and statuses check-setup.sh reports, so a
renamed check cannot leave the skill telling a session to look for a row that never
appears.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from basstler.regular_expression import (
    Anchor,
    CharacterRange,
    CharacterSet,
    RegularExpression,
)
from basstler.setup.report import CheckStatus, RepositoryCheck, SetupCheck

from basstler_testing.constants.paths import (
    RepositoryLocation,
    SkillDirectory,
    SkillFile,
)

SETUP_SKILL = (
    RepositoryLocation.PLUGIN
    / SkillDirectory.SETUP_PERSONAL_NOTES
    / SkillFile.INSTRUCTIONS
)
"""
The setup skill's own document.
"""


class RowReferenceGroup(StrEnum):
    """
    The part of a row reference read back from its match.
    """

    WORD = "word"
    """
    The check or status naming the row.
    """


CODE_QUOTE = "`"
"""
Encloses inline code.
"""

ROW = " row"
"""
The word after the code naming a row.
"""

PLURAL_ENDING = "s"
"""
What makes *row* plural.
"""

ROW_REFERENCE = RegularExpression.sequence(
    CODE_QUOTE,
    CharacterSet.any_of(CharacterRange.ASCII_LOWERCASE_LETTER, "_")
    .one_or_more()
    .captured_as(RowReferenceGroup.WORD),
    CODE_QUOTE,
    ROW,
    RegularExpression.sequence(PLURAL_ENDING).optional(),
    Anchor.WORD_BOUNDARY,
).compiled()
"""
How the skill names a row: by its check or by its status, in code, before the word
*row*.
"""

# %% the rows the skill names


@pytest.mark.parametrize(
    "word",
    sorted(
        {
            match[RowReferenceGroup.WORD]
            for match in ROW_REFERENCE.finditer(SETUP_SKILL.read_text(encoding="utf-8"))
        }
    ),
)
def test_every_row_the_setup_skill_names_is_one_check_setup_reports(word: str):
    """
    A word before *row* is either a check the script reports or a status it gives.
    """
    assert word in {*SetupCheck, *RepositoryCheck, *CheckStatus}

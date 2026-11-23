"""
Tests that the starter personal notes name nothing of basstler's, and that what they
once carried is shipped with basstler instead.

Notes a user is seeded with are copied once and never updated, so anything in them that
names a script, skill or module of basstler goes stale unnoticed when basstler changes.
What counts as basstler's is *derived* from the plugin and the package, so a name added
later is covered without this file being edited.
"""

from __future__ import annotations

from enum import StrEnum

import re

import pytest

from basstler.class_property import classproperty
from basstler.document_references import PACKAGE_NAME, CitedNames
from basstler.slash_command import SlashCommand
from basstler.github.constants import MarkdownSyntax
from basstler.locations import PluginLocation
from basstler.regular_expression import (
    ANY_CHARACTER_EXCEPT_LINE_BREAK,
    Anchor,
    CharacterClass,
    CharacterSet,
    RegularExpression,
)

from basstler_testing.constants.paths import (
    PersonalNotesPath,
    RepositoryLocation,
    SkillDirectory,
)

# %% what the starter notes may not name

STARTER_NOTES = (
    RepositoryLocation.PLUGIN / "skills" / "setup-personal-notes" / "starter-notes.md"
).read_text(encoding="utf-8")
"""
The starter notes as shipped.
"""

PULL_REQUEST_RULES = (
    RepositoryLocation.PLUGIN / SkillDirectory.PULL_REQUEST_RULES_DOCUMENT
).read_text(encoding="utf-8")
"""
The pull-request rules as shipped, which hold only while a skill linking them runs.
"""


class SectionGroup(StrEnum):
    """
    The part of a section heading read back from its match.
    """

    TITLE = "title"
    """
    The heading's text.
    """


class SectionHeading:
    """
    How a document's second-level sections are headed.
    """

    @classproperty
    def prefix(cls) -> str:
        """
        What a second-level Markdown heading starts with, as ``## ``.
        """
        return MarkdownSyntax.HEADING_MARKER * 2 + MarkdownSyntax.HEADING_SEPARATOR

    @classproperty
    def pattern(cls) -> re.Pattern[str]:
        """
        A second-level Markdown heading, capturing its title, as ``## Notes``.
        """
        return RegularExpression.sequence(
            Anchor.LINE_START,
            cls.prefix,
            ANY_CHARACTER_EXCEPT_LINE_BREAK.one_or_more().captured_as(
                SectionGroup.TITLE
            ),
            Anchor.LINE_END,
        ).compiled()


HOOK_SCRIPT_NAMES = sorted(
    script.name for script in RepositoryLocation.HOOKS.glob("*.sh")
)
"""
The file name of every script the plugin ships.
"""

SKILL_NAMES = sorted(
    skill.name
    for skill in (RepositoryLocation.PLUGIN / SkillDirectory.DIRECTORY).iterdir()
    if skill.is_dir()
)
"""
The name of every skill the plugin ships.
"""


def test_the_starter_notes_name_no_script_of_the_plugin():
    assert [name for name in HOOK_SCRIPT_NAMES if name in STARTER_NOTES] == []


@pytest.mark.parametrize("skill_name", SKILL_NAMES)
def test_the_starter_notes_invoke_no_skill_of_the_plugin(skill_name: str):
    """
    A skill's name appears neither as a slash command nor bare.
    """
    name_boundary = CharacterSet.any_of(CharacterClass.WORD_CHARACTER, "-")
    skill_mention = RegularExpression.sequence(
        RegularExpression.negative_lookbehind(name_boundary),
        RegularExpression.literal(SlashCommand.PREFIX).optional(),
        skill_name,
        RegularExpression.negative_lookahead(name_boundary),
    )
    assert skill_mention.compiled().search(STARTER_NOTES) is None


def test_the_starter_notes_cite_no_module_of_the_package():
    assert CitedNames.in_text(STARTER_NOTES).modules == frozenset()


@pytest.mark.parametrize(
    "name", [PACKAGE_NAME, PersonalNotesPath.LOCAL_INSTRUCTIONS.name]
)
def test_the_starter_notes_do_not_name_the_package_or_its_local_file(name: str):
    assert name.lower() not in STARTER_NOTES.lower()


# %% what ships with basstler instead


@pytest.mark.parametrize(
    "script",
    [
        PluginLocation.PLAN_SAVING_SCRIPT,
        PluginLocation.PULL_REQUEST_PROGRESS_SAVING_SCRIPT,
    ],
)
def test_the_session_rules_carry_the_instruction_that_names_each_script(
    script: PluginLocation,
):
    rules = (RepositoryLocation.PLUGIN / PluginLocation.SESSION_RULES).read_text(
        encoding="utf-8"
    )

    assert script.name in rules


def test_the_starter_notes_carry_no_section_of_the_pull_request_rules():
    """
    Notes reach every session, so a pull-request rule seeded into them would bind
    sessions that run no skill acting on pull requests.
    """
    assert (
        set(SectionHeading.pattern.findall(STARTER_NOTES))
        & set(SectionHeading.pattern.findall(PULL_REQUEST_RULES))
        == set()
    )

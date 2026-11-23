"""
The one thing about the resolve skill's upstream read worth asserting from code.

The skill is instructions, so most of what it says can only be checked by reading it.
The exception is what it must *not* condition on: a branch has an upstream pull request
from the moment its Create is clicked, while the promotion label appears only if someone
adds it afterwards, so the label is no evidence that the pull request exists. That is an
absence, computed from the stack tooling's own configuration rather than from a string
written here, which is what makes it worth a test where a prose assertion would not be.

Filesystem only: no network, no credentials, no scratch repository.
"""

from __future__ import annotations

from enum import StrEnum


from basstler.slash_command import SlashCommand
from basstler.github.stack_configuration import (
    CommittedStackConfiguration,
    StackSetting,
)
from basstler.regular_expression import Anchor, CharacterClass, RegularExpression

from basstler_testing.constants.paths import RepositoryLocation, SkillDirectory

# %% the documents under test


def skill_document(skill: SkillDirectory) -> str:
    """
    :param skill: The skill to read.
    :return: The skill's instructions.
    """
    return (RepositoryLocation.PLUGIN / skill / "SKILL.md").read_text(encoding="utf-8")


def promotion_label() -> str:
    """
    The fork-pull-request label a developer adds once they have promoted a branch.

    Read through the stack tooling's own configuration and the setting that owns the
    label, so renaming either reaches this test instead of leaving it asserting the
    absence of something nothing uses.

    :return: The label.
    """
    return CommittedStackConfiguration().values()[StackSetting.IN_REVIEW_LABEL]


class FrontMatterGroup(StrEnum):
    """
    The parts of a skill document's front matter read back from its match.
    """

    NAME = "name"
    """
    The skill's name.
    """


def upstream_reviews_invocation() -> str:
    """
    How a session invokes the upstream-reviews skill.

    :return: The slash command, read from the skill's own frontmatter.
    """
    frontmatter = skill_document(SkillDirectory.UPSTREAM_REVIEWS)
    name = (
        RegularExpression.sequence(
            Anchor.LINE_START,
            "name:",
            CharacterClass.WHITESPACE.zero_or_more(),
            CharacterClass.NON_WHITESPACE.one_or_more().captured_as(
                FrontMatterGroup.NAME
            ),
            CharacterClass.WHITESPACE.zero_or_more(),
            Anchor.LINE_END,
        )
        .compiled()
        .search(frontmatter)
    )
    return f"{SlashCommand.PREFIX}{name[FrontMatterGroup.NAME]}"


# %% the resolve skill's upstream read


def test_the_upstream_read_is_not_conditioned_on_the_promotion_label():
    """
    The label is hand-added after the fact, so gating on it skips exactly the branches
    most likely to be carrying upstream review comments.
    """
    instructions = skill_document(SkillDirectory.PLAN_ITEM_RESOLVE)

    assert promotion_label() not in instructions
    assert StackSetting.IN_REVIEW_LABEL not in instructions


def test_the_upstream_reviews_are_still_read():
    """
    Removing the condition must not remove the read it was conditioning.
    """
    instructions = skill_document(SkillDirectory.PLAN_ITEM_RESOLVE)

    assert upstream_reviews_invocation() in instructions

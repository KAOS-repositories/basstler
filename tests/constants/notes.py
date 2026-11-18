"""
Branch names and CLAUDE.local.md sections the personal-notes suites share.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.regular_expression import (
    ANY_CHARACTER,
    LINE_BREAK,
    CharacterSet,
    RegularExpression,
)
from basstler.render_common import HtmlSyntax
from basstler.setup.steps import PersonalNotesSetting


class ScratchBranch(StrEnum):
    """
    The branches a scratch repository is given besides a stack's own.
    """

    PERSONAL_NOTES = PersonalNotesSetting.BRANCH.default
    """
    The personal-notes branch name the hooks resolve to by default.
    """

    WORK = "some-work-branch"
    """
    The throwaway branch a scratch repository is left checked out on.
    """


class SectionMarker(StrEnum):
    """
    The text of the HTML comments that open and close a marked section.
    """

    BEGIN = "BEGIN-"
    """
    Precedes the section's name in the opening comment.
    """

    END = "END-"
    """
    Precedes the section's name in the closing comment.
    """

    LABEL_SEPARATOR = ": "
    """
    Separates the section's name from the label an opening comment may carry.
    """

    PADDING = " "
    """
    Separates a comment's text from its delimiters.
    """


class SectionGroup(StrEnum):
    """
    The part of a marked section read back from its match.
    """

    CONTENT = "content"
    """
    What lies between the section's markers.
    """


class ClaudeLocalSection(StrEnum):
    """
    The marked sections the shell hooks write into, and read back out of,
    :attr:`PersonalNotesPath.LOCAL_INSTRUCTIONS`.
    """

    SESSION_RULES = "SESSION-RULES"
    """
    The rules every session using basstler's skills follows.
    """

    PULL_REQUEST_PROGRESS = "PR-PROGRESS"
    """
    The current branch's pull request progress notes.
    """

    PLAN_ITEM = "PLAN-ITEM"
    """
    The plan item the current branch is tracked by.
    """

    PLAN_MANIFEST = "PLAN-MANIFEST"
    """
    A plan's manifest, as edited for :file:`save-plan.sh`.
    """

    PLAN_ROADMAP = "PLAN-ROADMAP"
    """
    A plan's roadmap, as edited for :file:`save-plan.sh`.
    """

    def around(self, content: str, label: str | None = None) -> str:
        """
        :param content: The section's content, ending in a newline.
        :param label: What the opening marker names after its colon, if anything.
        :return: *content* between this section's markers.
        """
        opening = (
            self if label is None else f"{self}{SectionMarker.LABEL_SEPARATOR}{label}"
        )
        return (
            f"{self.comment(SectionMarker.BEGIN + opening)}{LINE_BREAK}"
            f"{content}{self.comment(SectionMarker.END + self)}{LINE_BREAK}"
        )

    @staticmethod
    def comment(text: str) -> str:
        """
        :param text: What the comment says.
        :return: The HTML comment saying it.
        """
        return (
            f"{HtmlSyntax.COMMENT_START}{SectionMarker.PADDING}{text}"
            f"{SectionMarker.PADDING}{HtmlSyntax.COMMENT_END}"
        )

    def within(self, text: str) -> str:
        """
        :param text: A document holding this section once.
        :return: The section's content, without its markers.
        """
        label = RegularExpression.sequence(
            SectionMarker.LABEL_SEPARATOR,
            CharacterSet.any_except(HtmlSyntax.TAG_END).zero_or_more(),
        )
        pattern = RegularExpression.sequence(
            HtmlSyntax.COMMENT_START,
            SectionMarker.PADDING,
            SectionMarker.BEGIN,
            self,
            label.optional(),
            SectionMarker.PADDING,
            HtmlSyntax.COMMENT_END,
            LINE_BREAK,
            ANY_CHARACTER.zero_or_more(shortest=True).captured_as(SectionGroup.CONTENT),
            self.comment(SectionMarker.END + self),
        )
        return pattern.compiled().search(text)[SectionGroup.CONTENT]


class ProgressBranch(StrEnum):
    """
    The branches progress notes are kept for in the pruning suites, each standing for
    one state its pull request can be in.

    The ones with a pull request are those
    :attr:`DatasetLocation.PULL_REQUESTS_BY_BRANCH` records.
    """

    OPEN = "open-work"
    """
    Its pull request is open.
    """

    REOPENED = "reopened-work"
    """
    One pull request of it was closed, and a later one is open.
    """

    MERGED = "merged-work"
    """
    Its pull request merged.
    """

    DELETED = "claude/deleted-work"
    """
    Its pull request merged and the branch was deleted.
    """

    UNOPENED = "unopened-work"
    """
    It has no pull request yet.
    """

"""
The maintenance executor's hand-maintained values.

Everything here is a decision somebody made and may change again - the heading a promotion
link is written under, the label marking it sent. They are gathered in one module, each
in the enum of the values it is one of, so changing one is an edit rather than a search
through whichever module happens to read it.

Values a program derives for itself belong beside the code that derives them, not here.
"""

from __future__ import annotations

from enum import Enum, IntEnum, StrEnum

from basstler.regular_expression import (
    Anchor,
    CharacterClass,
    CharacterRange,
    CharacterSet,
    RegularExpression,
)


class GitHubExecutable(StrEnum):
    """
    The executables the tooling reaches the GitHub API through, each named as it is on
    ``PATH``.
    """

    COMMAND_LINE = "gh"
    """
    GitHub's own command-line client, preferred where it is installed.
    """

    CURL = "curl"
    """
    The plain HTTP client the shell hooks fall back to, with a token, where there is no
    ``gh``.
    """


class ClaudeCodeSessionLink(StrEnum):
    """
    The link to a Claude Code session.
    """

    URL_PREFIX = "https://claude.ai/code/session_"
    """
    Starts the link, before the session's identifier.
    """


class HeadingLevel(IntEnum):
    """
    The levels a Markdown heading may have, which is how many markers it starts with.
    """

    DEEPEST = 6
    """
    The most markers a heading may have.
    """


class DescriptionPattern(Enum):
    """
    What the tooling looks for in a pull request description.
    """

    SESSION_LINK = RegularExpression.sequence(
        ClaudeCodeSessionLink.URL_PREFIX,
        CharacterSet.any_of(
            CharacterRange.ASCII_ALPHANUMERIC,
            "_-",
        ).one_or_more(),
    ).compiled()
    """
    The session link a pull request description carries, which is the only channel for
    telling a branch's owner that their branch needs them.

    >>> pattern = DescriptionPattern.SESSION_LINK.value
    >>> pattern.search("Session: https://claude.ai/code/session_01Ab-c.")[0]
    'https://claude.ai/code/session_01Ab-c'
    """

    HEADING = RegularExpression.sequence(
        Anchor.LINE_START,
        RegularExpression.literal("#").repeated(1, HeadingLevel.DEEPEST),
        " ",
    ).compiled()
    r"""
    The start of a Markdown heading line, which ends the section before it.

    >>> DescriptionPattern.HEADING.value.findall("## Done\n#hashtag\n### Next")
    ['## ', '### ']
    """

    LINK_TARGET = RegularExpression.sequence(
        RegularExpression.lookbehind("]("),
        CharacterSet.any_except(")", CharacterClass.WHITESPACE).one_or_more(),
        RegularExpression.lookahead(")"),
    ).compiled()
    """
    The URL a Markdown hyperlink points at.

    >>> pattern = DescriptionPattern.LINK_TARGET.value
    >>> pattern.findall("[pull request](https://github.com/o/r/pull/1)")
    ['https://github.com/o/r/pull/1']
    """

    def first_in(self, text: str | None) -> str | None:
        """
        :param text: The text to search, which may be absent.
        :return: The first match, or ``None`` if the text holds none.
        """
        if not text:
            return None
        found = self.value.search(text)
        return found.group(0) if found else None


class MaintenanceText(StrEnum):
    """
    Text a maintenance pass writes onto GitHub, and later finds again by.
    """

    CONFLICT_COMMENT_PREFIX = "🔴 MAINTENANCE - NEEDS RESOLUTION:"
    """
    Opens the comment a conflict is reported in, so the branch's owner can find every one
    of them at a glance.
    """

    MERGE_RESOLUTION = (
        "Merge `{parent}` into this branch, resolve the conflicts in the merge commit "
        "and push. A plain push publishes it; the pass never force-pushes a merged branch."
    )
    """
    How the owner of a conflicting branch resolves it when the pass merges its parent,
    with the parent's name to fill in.
    """

    REBASE_RESOLUTION = (
        "Rebase this branch onto `{parent}`, resolve the conflicts and push with "
        "`--force-with-lease`. Its `rebase` label is what allows the rewrite."
    )
    """
    How the owner of a conflicting branch resolves it when the pass rebases it onto its
    parent, with the parent's name to fill in.
    """

    LANDED_COMMENT = (
        "Closed by a maintenance pass: every commit of `{branch}` is in `{base}`, so "
        "its work has landed. GitHub records no merge for a pull request that is not "
        "based on the branch it landed in, so it stayed open."
    )
    """
    What a pull request is told when it is closed because its work landed, with its
    branch and the upstream base to fill in.
    """

    PROMOTION_HEADING = "## Promote"
    """
    Heading the compare-and-create link is written under, in the fork pull request's own
    description - the summary that carried it is delivered once and then gone, and the
    description is still there a week later.
    """

    UPSTREAM_PULL_REQUEST_HEADING = "## Upstream pull request"
    """
    Heading the link to the open upstream pull request opened from the branch is written
    under, in the fork pull request's own description.
    """

    FULL_DETAIL = "Full detail:"
    """
    Opens the line an upstream pull request's description ends with, linking back to the
    fork pull request it was promoted from.
    """


class MaintenanceNotice(StrEnum):
    """
    What a maintenance command tells its caller on stderr about how it ran.
    """

    NO_UPSTREAM = (
        "no upstream is named, so the clone's own remote is the base: no upstream pull "
        "request is read and no branch is promoted"
    )
    """
    The project is not a fork, so the pass leaves out every step that needs an upstream.
    """

    LANDED_BRANCH_UNREADABLE = (
        "`{branch}` is in the upstream base but its commits cannot be counted, because "
        "`{base}` or `{head}` is not in this clone: its pull request was not closed. "
        "Fetch the fork and run the pass again."
    )
    """
    A landed branch was left open because the fork's copy of it or of its base is
    missing, with the branch and the two references to fill in.
    """


class MergeableState(StrEnum):
    """
    The values GitHub reports as a pull request's ``mergeable_state``.

    Only :attr:`DIRTY` means a branch genuinely conflicts with its base; every other one
    means there are no conflicts, whatever else may be true of it.
    """

    DIRTY = "dirty"
    """
    The branch conflicts with its base.
    """

    CLEAN = "clean"
    """
    Mergeable, with every required check passing.
    """

    UNSTABLE = "unstable"
    """
    Mergeable, with a check that is not required failing.
    """

    BLOCKED = "blocked"
    """
    Mergeable once a required review or check passes.
    """

    BEHIND = "behind"
    """
    Mergeable once brought up to date with its base.
    """

    HAS_HOOKS = "has_hooks"
    """
    Mergeable, with pre-receive hooks configured.
    """

    DRAFT = "draft"
    """
    A draft, which cannot be merged until it is marked ready.
    """

    UNKNOWN = "unknown"
    """
    Not yet computed by GitHub.
    """

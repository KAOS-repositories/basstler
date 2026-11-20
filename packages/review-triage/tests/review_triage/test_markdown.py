"""
Judging Markdown documentation whose python code blocks change.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from basstler.git.commit_range import FileVersions
from basstler.review_triage.comparison import (
    FileNeedingReview,
    FileTriager,
    FileVerdict,
    JudgmentContext,
    MechanicalFile,
)
from basstler.review_triage.definitions import DefinitionIndex, SourceDefinitions
from basstler.review_triage.keyword_arguments import KeywordChange
from basstler.review_triage.markdown import MarkdownComparison
from basstler.review_triage.renames import RenameMap

from basstler_testing.constants.paths import DatasetLocation

# %% verdicts

MARKDOWN_SAMPLES = DatasetLocation.REVIEW_TRIAGE / "markdown-code-blocks"
"""
The Markdown versions and the definitions their code blocks call.
"""


def change_to(head: str) -> FileVersions:
    """
    :param head: The name of the head version in :data:`MARKDOWN_SAMPLES`.
    :return: The change from the base version to it.
    """
    return FileVersions(
        PurePosixPath("guide.md"),
        base_text=(MARKDOWN_SAMPLES / "base.md").read_text(encoding="utf-8"),
        head_text=(MARKDOWN_SAMPLES / head).read_text(encoding="utf-8"),
    )


def triaged(head: str) -> FileVerdict:
    """
    :param head: The name of the head version in :data:`MARKDOWN_SAMPLES`.
    :return: The verdict on the change to it, the sample definitions as the base
        commit's.
    """
    definitions = (MARKDOWN_SAMPLES / "definitions.py").read_text(encoding="utf-8")
    context = JudgmentContext(
        RenameMap(), DefinitionIndex(SourceDefinitions((definitions,)))
    )
    return FileTriager(context, (MarkdownComparison(),)).triage(change_to(head))


# %% code blocks


def test_a_code_block_binding_as_before_is_mechanical():
    """
    Keywords naming the parameters a code block's call bound its arguments to are
    mechanical.
    """
    assert triaged("head.md") == MechanicalFile(
        change_to("head.md"), frozenset({KeywordChange.KEYWORD_ARGUMENTS})
    )


@pytest.mark.parametrize(
    "head",
    [
        "head-swapped.md",
        "head-prose-changed.md",
        "head-unparsable.md",
        "head-block-added.md",
    ],
)
def test_a_change_that_may_differ_in_meaning_needs_review(head: str):
    """
    Keywords naming other parameters, reworded prose, a block that does not parse and a
    block added need review.
    """
    assert triaged(head) == FileNeedingReview(change_to(head))

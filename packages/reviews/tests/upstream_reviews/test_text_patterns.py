"""
Tests for the patterns the upstream reviews tooling reads text with: the installed
workflow's branch or tag, one chunk of a helper's output, a runner's log line, and the
link of a check to its job.
"""

from __future__ import annotations

import pytest

from basstler.upstream_reviews.action.branch import (
    ActionInstallation,
    InstalledWorkflowGroup,
    ReviewsWorkflowInput,
)
from basstler.upstream_reviews.failure_logs import FailedJob, LogFormatting
from basstler.upstream_reviews.helper.recording import ChunkGroup, HelperChunk

# %% the installed workflow's branch or tag


@pytest.mark.parametrize(
    ("line", "branch_or_tag"),
    [
        (f"{ReviewsWorkflowInput.BRANCH_OR_TAG}: v4.2.2", "v4.2.2"),
        (f"    {ReviewsWorkflowInput.BRANCH_OR_TAG}:main  ", "main"),
        (f"{ReviewsWorkflowInput.BRANCH_OR_TAG}:", None),
        (f"# {ReviewsWorkflowInput.BRANCH_OR_TAG}: v1", None),
        (f"other_{ReviewsWorkflowInput.BRANCH_OR_TAG}: v1", None),
        ("uses: basstler/.github/workflows/upstream-reviews.yml@v1", None),
    ],
)
def test_the_branch_or_tag_is_read_from_the_line_naming_it(
    line: str, branch_or_tag: str | None
):
    """
    Each line of a workflow is listed beside the branch or tag read from it.
    """
    found = ActionInstallation.branch_or_tag_line.search(line)

    assert (
        found[InstalledWorkflowGroup.BRANCH_OR_TAG] if found else None
    ) == branch_or_tag


# %% a chunk of the helper's output


@pytest.mark.parametrize(
    ("text", "chunk"),
    [
        ("BASSTLER-UPSTREAM-REVIEWS-abc-1-3:QUJD+/=", (1, 3, "QUJD+/=")),
        ("quoted: `BASSTLER-UPSTREAM-REVIEWS-abc-12-30:Zm9v` end", (12, 30, "Zm9v")),
        ("BASSTLER-UPSTREAM-REVIEWS-other-1-3:QUJD", None),
        ("BASSTLER-UPSTREAM-REVIEWS-abc-x-3:QUJD", None),
        ("BASSTLER-UPSTREAM-REVIEWS-abc-1-3:", None),
        ("BASSTLER-UPSTREAM-REVIEWS-abc-1-3 QUJD", None),
    ],
)
def test_a_chunk_of_the_request_is_read_wherever_it_is_quoted(
    text: str, chunk: tuple[int, int, str] | None
):
    """
    Each text is listed beside the index, count and text of the chunk found in it.
    """
    found = HelperChunk.pattern("abc").search(text)

    assert (
        (
            int(found[ChunkGroup.INDEX]),
            int(found[ChunkGroup.COUNT]),
            found[ChunkGroup.TEXT],
        )
        if found
        else None
    ) == chunk


# %% a runner's log line


@pytest.mark.parametrize(
    ("line", "text"),
    [
        ("2026-11-23T00:11:26.7990077Z ##[error]failed", "##[error]failed"),
        ("2026-11-23T00:11:26Z \x1b[31;1mred\x1b[0m text", "red text"),
        ("\x1b[0m", ""),
        ("no timestamp, \x1b[1mbold\x1b[m", "no timestamp, bold"),
        ("2026-11-23T00:11:26Zno separator", "2026-11-23T00:11:26Zno separator"),
        ("plain", "plain"),
    ],
)
def test_the_timestamp_and_colour_of_a_log_line_are_removed(line: str, text: str):
    """
    Each log line is listed beside the text left once its formatting is removed.
    """
    assert LogFormatting.remove_from(line) == text


# %% the link of a check to its job


@pytest.mark.parametrize(
    ("link", "identifier"),
    [
        ("https://github.com/o/r/actions/runs/123/job/456", "456"),
        ("https://github.com/o/r/actions/runs/1/job/22?pr=5", "22"),
        ("https://github.com/o/r/actions/runs/123", None),
        ("https://github.com/o/r/actions/runs/x/job/456", None),
        ("https://github.com/o/r/runs/123/job/456", None),
        ("https://ci.example.com/build/9", None),
    ],
)
def test_the_job_of_a_check_is_read_from_its_link(link: str, identifier: str | None):
    """
    Each link is listed beside the job number read from it.
    """
    found = FailedJob.link_pattern.search(link)

    assert (found[FailedJob.identifier_group] if found else None) == identifier

"""
Leaving one mechanical file per rename for review, so a reviewer still sees each new
name.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from basstler.git.commit_range import FileVersions
from basstler.locations import ReviewTriageLocation
from basstler.github.graphql import GraphQLRequest
from basstler.review_triage.comparison import MechanicalFile
from basstler.review_triage.outputs import MarkdownReport, ViewedFile, ViewedMarking
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.review_samples import ReviewSample, ReviewSampling
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

from ..scratch_repository import ScratchRepository
from .conftest import RecordingWriter, committed_pull_request
from .samples import (
    DefinitionMoveSample,
    RenameMixedSample,
    RenameSampledSample,
    SampleTrees,
)

# %% helpers


def sampled_triage(
    scratch_repository: ScratchRepository, base: SampleTrees, head: SampleTrees
) -> TriageOutcome:
    """
    :param scratch_repository: The repository to commit in.
    :param base: The sample's base tree.
    :param head: The sample's head tree.
    :return: The sample pull request's triage, leaving samples.
    """
    changes = committed_pull_request(scratch_repository, base, head)
    return PullRequestTriager(sampling=ReviewSampling()).triage(changes)


def sampled_renames(outcome: TriageOutcome) -> list[tuple[str, str, PurePosixPath]]:
    """
    :param outcome: A triage.
    :return: Each sample's rename and file.
    """
    return [
        (sample.rename.old, sample.rename.new, sample.path)
        for sample in outcome.samples
    ]


# %% choosing the samples


def test_each_rename_is_sampled_where_its_new_name_is_defined(
    scratch_repository: ScratchRepository,
):
    outcome = sampled_triage(
        scratch_repository,
        RenameSampledSample.BASE_TREE,
        RenameSampledSample.HEAD_TREE,
    )
    scores = PurePosixPath("pkg/scores.py")
    assert sampled_renames(outcome) == [
        ("rank_of_right", "get_rank_of_confirmed", scores),
        ("ranked_first", "count_ranked_first", scores),
    ]


def test_sampled_files_are_left_out_of_the_files_marked_viewed(
    scratch_repository: ScratchRepository,
):
    outcome = sampled_triage(
        scratch_repository,
        RenameSampledSample.BASE_TREE,
        RenameSampledSample.HEAD_TREE,
    )
    assert [file.change.path for file in outcome.files_to_mark_viewed] == [
        PurePosixPath("pkg/report.py")
    ]


def test_a_rename_a_file_needing_review_shows_is_not_sampled(
    scratch_repository: ScratchRepository,
):
    """
    The module defining both new names changes a default value too, so the reviewer
    reads it anyway.
    """
    outcome = sampled_triage(
        scratch_repository, RenameMixedSample.BASE_TREE, RenameMixedSample.HEAD_TREE
    )
    assert outcome.samples == ()


def test_a_move_is_not_sampled(scratch_repository: ScratchRepository):
    outcome = sampled_triage(
        scratch_repository,
        DefinitionMoveSample.BASE_TREE,
        DefinitionMoveSample.HEAD_TREE,
    )
    assert outcome.samples == ()


def test_a_rename_defined_elsewhere_is_sampled_where_it_is_used_most(
    old_name_renamed: RenameMap,
):
    once = MechanicalFile(
        FileVersions(
            PurePosixPath("a.py"),
            base_text="value = old_name()",
            head_text="value = new_name()",
        )
    )
    twice = MechanicalFile(
        FileVersions(
            PurePosixPath("b.py"),
            base_text="value = old_name() + old_name()",
            head_text="value = new_name() + new_name()",
        )
    )
    assert ReviewSampling().samples(old_name_renamed, (once, twice)) == (
        ReviewSample(old_name_renamed.renames[0], twice.change.path),
    )


# %% the outputs


def test_sampled_files_are_not_marked_viewed(scratch_repository: ScratchRepository):
    outcome = sampled_triage(
        scratch_repository,
        RenameSampledSample.BASE_TREE,
        RenameSampledSample.HEAD_TREE,
    )
    writer = RecordingWriter({"data": {}})
    ViewedMarking(writer).publish(outcome)
    document = ReviewTriageLocation.MARK_FILE_AS_VIEWED.read_text()
    assert writer.sent == [
        GraphQLRequest(
            document,
            ViewedFile(
                outcome.pull_request.node_identifier, file.change.path
            ).to_json(),
        )
        for file in outcome.files_to_mark_viewed
    ]


def test_the_report_names_each_sample_and_its_rename(
    scratch_repository: ScratchRepository,
):
    outcome = sampled_triage(
        scratch_repository,
        RenameSampledSample.BASE_TREE,
        RenameSampledSample.HEAD_TREE,
    )
    report = MarkdownReport().render(outcome)
    lines = [
        f"- `{sample.path}`: `{sample.rename.old}` → `{sample.rename.new}`"
        for sample in outcome.samples
    ]
    assert [line in report for line in lines] == [True] * len(outcome.samples)

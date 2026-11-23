"""
Triaging a whole pull request committed to a scratch repository, and publishing the
triage.
"""

from __future__ import annotations

from dataclasses import replace
from http import HTTPStatus
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from basstler.git.commands import GitCommandRunner
from basstler.github.exceptions import GraphQLErrorsReturned
from basstler.github.graphql import GraphQLRequest
from basstler.github.pull_request_changes import (
    PullRequestChanges,
    PullRequestChangesReader,
    RestPullRequest,
)
from basstler.review_triage.locations import ReviewTriageLocation
from basstler.review_triage.comparison import MechanicalChange
from basstler.review_triage.declaration import ArgumentDeclaration, TriageDeclaration
from basstler.review_triage.detection import RenameDetection
from basstler.review_triage.exceptions import PullRequestHeadMoved
from basstler.review_triage.outputs import MarkdownReport, ViewedFile, ViewedMarking
from basstler.review_triage.renames import Rename, RenameDecisions
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import (
    SAMPLE_REPOSITORY,
    FileListingWriter,
    listing_of,
    OnePullRequestReader,
    RecordingWriter,
    RefusingWriter,
    read_sample,
)
from .samples import DescriptionSample, PullRequestSample

# %% renames

MECHANICAL_KINDS = {
    PurePosixPath("caller.py"): frozenset(
        {MechanicalChange.IMPORTS, MechanicalChange.RENAME}
    ),
    PurePosixPath("helpers.py"): frozenset({MechanicalChange.RENAME}),
    PurePosixPath("notes.md"): frozenset({MechanicalChange.RENAME}),
    PurePosixPath("package/constants.py"): frozenset({MechanicalChange.MOVE}),
}
"""
What each mechanical file of the sample pull request changes.
"""


def mechanical_kinds(triage: TriageOutcome) -> dict[PurePosixPath, frozenset]:
    """
    :param triage: A triaged pull request.
    :return: The kinds of change of each of its mechanical files, by path.
    """
    return {file.change.path: file.kinds for file in triage.mechanical_files}


def test_a_consistent_rename_gone_from_the_head_is_detected(
    sample_changes: PullRequestChanges,
):
    """
    An identifier replaced everywhere by one absent from the base is detected as a
    rename.
    """
    assert RenameDetection().decisions(sample_changes) == RenameDecisions(
        (Rename("old_name", "new_name", RenameDetection()),)
    )


# %% the verdicts


def test_the_files_changed_only_mechanically_are_found(
    sample_changes: PullRequestChanges,
):
    """
    The renamed, imported and moved files are mechanical, each with its kinds.
    """
    assert mechanical_kinds(PullRequestTriager().triage(sample_changes)) == (
        MECHANICAL_KINDS
    )


def test_the_other_files_need_review(sample_changes: PullRequestChanges):
    """
    The added file and the file whose behaviour changed need review.
    """
    triage = PullRequestTriager().triage(sample_changes)
    assert {file.change.path for file in triage.files_needing_review} == {
        PurePosixPath("added.py"),
        PurePosixPath("geometry.py"),
    }


def test_a_rename_the_description_rejects_is_not_applied(
    scratch_repository: ScratchRepository, sample_payload: dict[str, Any]
):
    """
    Rejecting the detected rename leaves only the moved file mechanical.
    """
    changes = read_sample(
        scratch_repository, sample_payload, DescriptionSample.REJECTING_RENAME
    )
    assert mechanical_kinds(PullRequestTriager().triage(changes)) == {
        PurePosixPath("package/constants.py"): frozenset({MechanicalChange.MOVE})
    }


def test_a_rename_rejected_by_argument_is_not_applied(
    sample_changes: PullRequestChanges,
):
    """
    A rejection given as an argument outranks the detected rename, as the description's
    does.
    """
    default = PullRequestTriager()
    triager = replace(
        default,
        rename_sources=(
            *default.rename_sources,
            ArgumentDeclaration(TriageDeclaration(rejected_renames=("old_name",))),
        ),
    )
    assert mechanical_kinds(triager.triage(sample_changes)) == {
        PurePosixPath("package/constants.py"): frozenset({MechanicalChange.MOVE})
    }


# %% outputs


def test_the_report_lists_renames_and_both_groups_of_files(
    sample_changes: PullRequestChanges,
):
    """
    The Markdown report names the renames, the files needing review and the mechanical
    ones.
    """
    triage = PullRequestTriager().triage(sample_changes)
    expected = PullRequestSample.REPORT.path.read_text(encoding="utf-8").removesuffix(
        "\n"
    )
    assert MarkdownReport().render(triage) == expected


def test_each_mechanical_file_is_marked_viewed(sample_changes: PullRequestChanges):
    """
    One mutation is sent per mechanical file, naming the pull request and the file.
    """
    triage = PullRequestTriager().triage(sample_changes)
    writer = listing_of(triage)
    ViewedMarking(writer).publish(triage)
    document = ReviewTriageLocation.MARK_FILE_AS_VIEWED.read_text(encoding="utf-8")
    assert [request for request in writer.sent if request.query == document] == [
        GraphQLRequest(
            document,
            ViewedFile(triage.pull_request.node_identifier, path).to_json(),
        )
        for path in MECHANICAL_KINDS
    ]


def test_a_file_github_does_not_list_is_not_marked_viewed(
    sample_changes: PullRequestChanges,
):
    """
    A mechanical file GitHub does not count in the pull request, such as the old path of
    a file whose move GitHub pairs and git does not, is left out of the marking.
    """
    triage = PullRequestTriager().triage(sample_changes)
    unlisted, *listed = MECHANICAL_KINDS
    writer = FileListingWriter(triage.pull_request.head.commit, (tuple(listed),))
    ViewedMarking(writer).publish(triage)
    assert writer.marked_paths == listed


def test_a_file_on_a_later_page_is_marked_viewed(sample_changes: PullRequestChanges):
    """
    Every page of GitHub's listing counts, not only the first.
    """
    triage = PullRequestTriager().triage(sample_changes)
    writer = FileListingWriter(
        triage.pull_request.head.commit,
        tuple((file.change.path,) for file in triage.files),
    )
    ViewedMarking(writer).publish(triage)
    assert writer.marked_paths == list(MECHANICAL_KINDS)


def test_a_pull_request_pushed_to_since_its_triage_has_nothing_marked(
    sample_changes: PullRequestChanges,
):
    """
    When the head commit moved after the triage, no file is marked viewed.
    """
    triage = PullRequestTriager().triage(sample_changes)
    writer = replace(listing_of(triage), head_commit=triage.pull_request.base.commit)
    with pytest.raises(PullRequestHeadMoved):
        ViewedMarking(writer).publish(triage)
    assert writer.marked_paths == []


def test_a_viewed_path_is_sent_with_forward_slashes():
    """
    A file's path goes to GitHub as its POSIX form, on every platform.
    """
    path = PurePosixPath("package/constants.py")
    assert ViewedFile("node", path).to_json()["path"] == path.as_posix()


def test_a_refused_marking_is_raised(sample_changes: PullRequestChanges):
    """
    Errors in GitHub's answer are raised rather than ignored.
    """
    triage = PullRequestTriager().triage(sample_changes)
    writer = RecordingWriter({"errors": [{"message": "Resource not accessible"}]})
    with pytest.raises(GraphQLErrorsReturned):
        ViewedMarking(writer).publish(triage)


def test_a_refused_call_is_raised_as_a_refused_marking(
    sample_changes: PullRequestChanges,
):
    """
    A call GitHub refuses outright, as a session without GraphQL access gets, is raised
    as a refused marking, which names the other ways to mark the files.
    """
    triage = PullRequestTriager().triage(sample_changes)
    with pytest.raises(GraphQLErrorsReturned):
        ViewedMarking(RefusingWriter(HTTPStatus.FORBIDDEN)).publish(triage)


# %% reading in a checkout lacking the pull request


def test_a_checkout_lacking_the_commits_fetches_them(
    scratch_repository: ScratchRepository,
    sample_payload: dict[str, Any],
    sample_changes: PullRequestChanges,
    tmp_path: Path,
):
    """
    A checkout that has never seen the pull request's commits fetches them from the
    repository, then reads the same changes.
    """
    scratch_repository.serve_origin_as(SAMPLE_REPOSITORY.clone_url)
    pull_request = RestPullRequest.from_json(sample_payload)
    scratch_repository.run_git(
        "push",
        "--quiet",
        "origin",
        f"{pull_request.base.commit}:refs/heads/{pull_request.base.branch}",
        f"{pull_request.head.commit}:{pull_request.head_reference}",
    )
    # An empty checkout, whose fetches from the repository's GitHub URL git sends to
    # the scratch repository's remote instead, which holds both commits.
    reviewer = GitCommandRunner(tmp_path / "reviewer")
    reviewer.working_directory.mkdir()
    reviewer.run("init", "--quiet")
    reviewer.run(
        "config",
        f"url.{scratch_repository.work_remote_path}.insteadOf",
        SAMPLE_REPOSITORY.clone_url,
    )
    changes = PullRequestChangesReader(
        reviewer, OnePullRequestReader(sample_payload)
    ).read(SAMPLE_REPOSITORY, pull_request.number)
    assert changes.files == sample_changes.files

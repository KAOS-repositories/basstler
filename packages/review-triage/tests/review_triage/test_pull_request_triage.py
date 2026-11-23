"""
Triaging a whole pull request committed to a scratch repository, and publishing the
triage.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from basstler.git.commands import GitCommandRunner
from basstler.github.client import RetryPolicy
from basstler.github.exceptions import GraphQLErrorsReturned
from basstler.github.pull_request_changes import (
    MergeBaseStart,
    PullRequestChanges,
    PullRequestChangesReader,
    RestPullRequest,
)
from basstler.review_triage.comparison import FileNeedingReview, MechanicalChange
from basstler.review_triage.declaration import ArgumentDeclaration, TriageDeclaration
from basstler.review_triage.detection import RenameDetection
from basstler.review_triage.exceptions import PullRequestHeadMoved
from basstler.review_triage.keyword_arguments import (
    UnprovenBinding,
    UnprovenKeywordCall,
)
from basstler.review_triage.outputs import (
    MarkdownReport,
    TriageSummary,
    ViewedFiles,
    ViewedFilesVariable,
    ViewedMarking,
)
from basstler.review_triage.renames import Rename, RenameDecisions, RenameMap
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

from basstler_testing.scratch_repository import ScratchRepository
from .conftest import (
    SAMPLE_REPOSITORY,
    FileListingWriter,
    listing_of,
    flaky_listing_of,
    OnePullRequestReader,
    RecordingWriter,
    RefusingWriter,
    commit_trees,
    pull_request_between,
    read_sample,
)
from .samples import DescriptionSample, FileSample, PullRequestSample

INSTANT_RETRIES = RetryPolicy(first_delay=timedelta(0))
"""
A retry policy that asks again at once, so no test waits.
"""

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


def test_files_judged_in_other_processes_get_the_same_verdicts(
    sample_changes: PullRequestChanges,
):
    """
    Judging the files in several processes, a few at a time, gives each the verdict it
    gets judged in this process.
    """
    parallel = replace(
        PullRequestTriager(), workers=2, files_per_worker=1, files_per_batch=2
    )
    assert parallel.triage(sample_changes) == PullRequestTriager(workers=1).triage(
        sample_changes
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


def test_a_module_that_does_not_parse_needs_review(
    scratch_repository: ScratchRepository,
):
    """
    A module one version of which is not valid Python, such as one holding merge
    conflict markers, needs review.
    """
    sample = FileSample.CONFLICT_MARKERS.change()
    module = Path("point.py")
    changes = pull_request_between(
        commit_trees(
            scratch_repository,
            {module: sample.base_text},
            {module: sample.head_text},
        )
    )
    triage = PullRequestTriager().triage(changes)
    assert triage.files_needing_review == (FileNeedingReview(changes.files[0]),)


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


def test_a_rename_declared_by_argument_is_applied(
    sample_changes: PullRequestChanges, old_name_renamed: RenameMap
):
    """
    A rename given as an argument is applied, as the detected one is.
    """
    default = PullRequestTriager()
    triager = replace(
        default,
        rename_sources=(
            *default.rename_sources,
            ArgumentDeclaration(TriageDeclaration(old_name_renamed.replacements)),
        ),
    )
    assert mechanical_kinds(triager.triage(sample_changes)) == MECHANICAL_KINDS


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


def test_the_report_leaves_out_the_paths_of_moved_files(
    sample_changes: PullRequestChanges,
):
    """
    A moved file's path rename is seen in the move itself, so the table leaves it out.
    """
    triage = PullRequestTriager().triage(sample_changes)
    moved = [rename for rename in triage.renames.renames if rename.is_file_path]
    report = MarkdownReport().render(triage)
    rows = [f"| `{rename.old}` | `{rename.new}` |" in report for rename in moved]
    assert rows == [False] * len(moved)
    assert moved != []


def test_the_report_names_why_a_file_needs_review(sample_changes: PullRequestChanges):
    """
    Each reason a file needs review is listed under it, with its line.
    """
    triage = PullRequestTriager().triage(sample_changes)
    reason = UnprovenKeywordCall(
        3, "plot", UnprovenBinding.RECEIVER_CLASS_UNKNOWN, ("GoalPlotter.plot",)
    )
    explained = replace(triage.files_needing_review[0], reasons=(reason,))
    triage = replace(
        triage,
        files=tuple(
            explained if verdict.change == explained.change else verdict
            for verdict in triage.files
        ),
    )
    line = f"  - line {reason.line}: {reason.explanation}"
    assert line in MarkdownReport().render(triage).splitlines()


def test_the_summary_is_the_reports_count_of_files_needing_review(
    sample_changes: PullRequestChanges,
):
    """
    The summary is the line of the report counting the files that need review.
    """
    triage = PullRequestTriager().triage(sample_changes)
    summary = TriageSummary().render(triage)
    assert summary in MarkdownReport().render(triage).splitlines()
    assert summary.startswith(
        f"**{len(triage.files_needing_review)} of {len(triage.files)} files"
    )


def test_every_mechanical_file_is_marked_viewed_in_one_request(
    sample_changes: PullRequestChanges,
):
    """
    One request marks every mechanical file, naming the pull request and the files.
    """
    triage = PullRequestTriager().triage(sample_changes)
    writer = listing_of(triage)
    ViewedMarking(writer).publish(triage)
    assert writer.markings == [
        ViewedFiles(
            triage.pull_request.node_identifier, tuple(MECHANICAL_KINDS)
        ).request()
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


def test_mechanical_files_beyond_one_request_are_marked_in_several(
    sample_changes: PullRequestChanges,
):
    """
    No request marks more files than one request may.
    """
    triage = PullRequestTriager().triage(sample_changes)
    writer = listing_of(triage)
    ViewedMarking(writer, files_per_request=3).publish(triage)
    paths = tuple(MECHANICAL_KINDS)
    node = triage.pull_request.node_identifier
    assert writer.markings == [
        ViewedFiles(node, paths[:3]).request(),
        ViewedFiles(node, paths[3:]).request(),
    ]


def test_a_request_answered_with_a_server_error_is_sent_again(
    sample_changes: PullRequestChanges,
):
    """
    Marking files viewed is idempotent, so a request GitHub answers with a server error
    is sent again, and the marking succeeds once GitHub answers.
    """
    triage = PullRequestTriager().triage(sample_changes)
    writer = flaky_listing_of(triage, failures=2)
    ViewedMarking(writer, retry_policy=INSTANT_RETRIES).publish(triage)
    request = ViewedFiles(
        triage.pull_request.node_identifier, tuple(MECHANICAL_KINDS)
    ).request()
    assert writer.markings == [request] * 3


def test_a_request_answered_with_server_errors_throughout_is_raised_after_the_retries(
    sample_changes: PullRequestChanges,
):
    """
    A request still answered with a server error after the retry policy's last retry is
    raised as a refused marking.
    """
    triage = PullRequestTriager().triage(sample_changes)
    writer = flaky_listing_of(triage, failures=100)
    with pytest.raises(GraphQLErrorsReturned):
        ViewedMarking(writer, retry_policy=INSTANT_RETRIES).publish(triage)
    assert len(writer.markings) == 1 + INSTANT_RETRIES.retries


def test_each_viewed_file_is_its_own_mutation_of_the_request():
    """
    The request runs the mutation marking a file viewed once per file, each with that
    file's path, sent in its POSIX form on every platform.
    """
    paths = (PurePosixPath("package/constants.py"), PurePosixPath("notes.md"))
    request = ViewedFiles("node", paths).request()
    path_variables = {
        name: value
        for name, value in request.variables.items()
        if name != ViewedFilesVariable.PULL_REQUEST
    }
    assert sorted(path_variables.values()) == sorted(path.as_posix() for path in paths)
    assert request.query.count("markFileAsViewed(") == len(paths)
    assert all(f"path: ${name}" in request.query for name in path_variables)


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
    ).read(SAMPLE_REPOSITORY, pull_request.number, MergeBaseStart())
    assert changes.files == sample_changes.files

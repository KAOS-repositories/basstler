"""
Triaging each file of a pull request from where the viewer last viewed it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path, PurePosixPath

import pytest

from basstler.git.commands import GitCommandRunner
from basstler.git.commit_range import CommitRange
from basstler.github.pull_request_changes import (
    PullRequestChangesReader,
    StartCommit,
    StartReason,
)
from basstler.review_triage.comparison import FileNeedingReview, MechanicalFile
from basstler.review_triage.exceptions import PullRequestHeadMoved
from basstler.review_triage.file_listing import (
    FileListingReader,
    FileViewedState,
    GraphQLAttempts,
)
from basstler.review_triage.outputs import ViewedMarking
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome
from basstler.locations import ProjectLocation
from basstler.personal_notes.contribution import SetupPersonalNotesSkill
from basstler.review_triage.viewed_states import (
    ClonedViewedCheckpoints,
    NotesBranchViewedCheckpoints,
    ViewedCheckpointFile,
    ViewedCheckpoints,
    ViewedFilesTriage,
)
from basstler.shell_configuration import PersonalNotesSetting

from basstler_testing.constants.notes import ScratchBranch
from basstler_testing.scratch_repository import ScratchRepository
from .conftest import (
    SAMPLE_REPOSITORY,
    FileListingWriter,
    RefusingWriter,
    ReviewedPullRequestReader,
)
from .samples import PullRequestSample, ViewedStateSample

# %% the sample

NEVER_VIEWED = PurePosixPath("reformatted.py")
"""
A file the viewer never viewed, its imports reordered.
"""

VIEWED = PurePosixPath("viewed.py")
"""
A file the viewer viewed at the head.
"""

REVIEWED = PurePosixPath("reviewed.py")
"""
A file the viewer viewed at the first commit, its imports reordered since.
"""

UNRECORDED = PurePosixPath("unrecorded.py")
"""
A file changed as :data:`REVIEWED` was, viewed at a commit nothing recorded.
"""

VIEWED_STATES = {VIEWED: FileViewedState.VIEWED, REVIEWED: FileViewedState.DISMISSED}
"""
The viewer's state of each file GitHub lists other than unviewed.
"""


@dataclass(frozen=True)
class ViewedHistory:
    """
    The sample committed: its base, the commit the viewer viewed files at, and its head.
    """

    repository: ScratchRepository
    """
    The repository holding the commits.
    """

    commits: CommitRange
    """
    The base and the head commit.
    """

    checkpoint: str
    """
    The commit the viewer viewed :data:`REVIEWED` and :data:`UNRECORDED` at.
    """

    checkpoints: ViewedCheckpoints
    """
    Where the heads files were seen viewed at are kept.
    """

    def triage(
        self,
        listing_writer: FileListingWriter | RefusingWriter | None = None,
        account: dict[str, str] | None = None,
    ) -> TriageOutcome:
        """
        :param listing_writer: What answers the file listing; the sample's states at
            the head by default.
        :param account: The account the credential belongs to, ``None`` for one GitHub
            names no account for.
        :return: The sample triaged from where each file was last viewed.
        """
        payload = PullRequestSample.PAYLOAD.payload()
        payload["base"]["sha"] = self.commits.base_commit
        payload["head"]["sha"] = self.commits.head_commit
        reader = ReviewedPullRequestReader(payload, account, [])
        return ViewedFilesTriage(
            PullRequestTriager(),
            PullRequestChangesReader(self.repository.git, reader),
            SAMPLE_REPOSITORY,
            FileListingReader(GraphQLAttempts(listing_writer or self.listing())),
            self.checkpoints,
        ).outcome(payload["number"])

    def listing(self, head_commit: str | None = None) -> FileListingWriter:
        """
        :param head_commit: The head the listing reports, the sample's by default.
        :return: A listing of every file of the sample in its viewed state.
        """
        paths = tuple(
            PurePosixPath(path) for path in ViewedStateSample.HEAD_TREE.files()
        )
        return FileListingWriter(
            head_commit or self.commits.head_commit, (paths,), dict(VIEWED_STATES)
        )


@pytest.fixture
def viewed_history(
    scratch_repository: ScratchRepository, tmp_path: Path
) -> ViewedHistory:
    """
    :return: The sample committed, nothing recorded about where files were viewed.
    """
    for tree in (
        ViewedStateSample.BASE_TREE,
        ViewedStateSample.CHECKPOINT_TREE,
        ViewedStateSample.HEAD_TREE,
    ):
        for path, text in tree.files().items():
            scratch_repository.write(path, text)
        scratch_repository.commit_everything(tree)
    git = scratch_repository.git
    return ViewedHistory(
        scratch_repository,
        CommitRange(git, git.commit_at("HEAD~2"), git.commit_at("HEAD")),
        git.commit_at("HEAD~1"),
        ClonedViewedCheckpoints(tmp_path / "checkpoints.json"),
    )


def verdict_of(outcome: TriageOutcome, path: PurePosixPath) -> type:
    """
    :param outcome: A triaged pull request.
    :param path: One of its files.
    :return: The kind of verdict on the file.
    """
    return type(next(file for file in outcome.files if file.change.path == path))


# %% each file's start


def test_a_file_viewed_at_its_current_content_is_left_out(viewed_history):
    """
    The viewer has seen the file as it is, so it is neither judged nor marked again.
    """
    outcome = viewed_history.triage()
    assert (
        outcome.viewed_files,
        VIEWED in {file.change.path for file in outcome.files},
    ) == (
        frozenset({VIEWED}),
        False,
    )


def test_a_file_never_viewed_is_judged_from_the_merge_base(viewed_history):
    """
    A file whose imports alone change is mechanical over the whole change.
    """
    assert verdict_of(viewed_history.triage(), NEVER_VIEWED) is MechanicalFile


def test_a_file_changed_since_it_was_viewed_is_judged_from_where_it_was_viewed(
    viewed_history,
):
    """
    The viewer read the file's change up to the commit it was viewed at, and only its
    imports changed since.
    """
    viewed_history.checkpoints.record(viewed_history.checkpoint, frozenset({REVIEWED}))
    assert verdict_of(viewed_history.triage(), REVIEWED) is MechanicalFile


def test_a_file_changed_since_it_was_viewed_where_nothing_recorded_is_judged_whole(
    viewed_history,
):
    """
    Without the commit it was viewed at, the file's whole change is judged, which
    changes its value.
    """
    assert verdict_of(viewed_history.triage(), REVIEWED) is FileNeedingReview


def test_a_file_viewed_at_a_commit_the_head_does_not_contain_is_judged_whole(
    viewed_history,
):
    """
    A commit pushed over, such as before a rebase, says nothing of the head's history.
    """
    repository = viewed_history.repository
    repository.run_git("checkout", "--quiet", "--detach", viewed_history.checkpoint)
    repository.write(str(REVIEWED), "VALUE = 1\n")
    repository.commit_everything("pushed over")
    pushed_over = repository.git.commit_at("HEAD")
    viewed_history.checkpoints.record(pushed_over, frozenset({REVIEWED}))
    assert verdict_of(viewed_history.triage(), REVIEWED) is FileNeedingReview


def test_the_files_viewed_at_the_head_are_recorded_as_viewed_there(viewed_history):
    """
    A file the viewer has viewed changes again later; it is then judged from here.
    """
    viewed_history.triage()
    assert viewed_history.checkpoints.read() == {
        VIEWED: viewed_history.commits.head_commit
    }


# %% marking


def test_marking_records_the_marked_files_as_viewed_at_the_head(viewed_history):
    """
    The files marked viewed are judged from the head once they change again.
    """
    outcome = viewed_history.triage()
    ViewedMarking(
        viewed_history.listing(), checkpoints=viewed_history.checkpoints
    ).publish(outcome)
    head = viewed_history.commits.head_commit
    assert viewed_history.checkpoints.read() == {
        VIEWED: head,
        **{file.change.path: head for file in outcome.mechanical_files},
    }


# %% the listing


def test_without_the_listing_the_triage_starts_where_the_last_review_starts(
    viewed_history,
):
    """
    A credential GraphQL refuses, as in a cloud session, triages from the last review,
    here the merge base for an account GitHub names nobody for.
    """
    outcome = viewed_history.triage(RefusingWriter(HTTPStatus.FORBIDDEN))
    assert outcome.start == StartCommit(
        viewed_history.commits.base_commit, StartReason.MERGE_BASE
    )


def test_a_listing_at_another_head_is_refused(viewed_history):
    """
    The viewed states of another head say nothing of this one's files.
    """
    with pytest.raises(PullRequestHeadMoved):
        viewed_history.triage(viewed_history.listing(viewed_history.checkpoint))


# %% where the checkpoints are kept

CHECKPOINTED_PULL_REQUEST = 7
"""
The number of the pull request whose checkpoints the tests below keep.
"""


@pytest.fixture
def notes_branch_reached(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    :return: A clone whose personal-notes setting names a remote holding the branch.
    """
    scratch_repository.publish_notes_branch(
        {ProjectLocation.PERSONAL_NOTES_DOCUMENT: ""}
    )
    scratch_repository.run_git(
        "config",
        PersonalNotesSetting.REMOTE.git_config_key,
        scratch_repository.notes_remote_path.as_posix(),
    )
    return scratch_repository


def test_checkpoints_are_pushed_to_the_personal_notes_branch_where_a_remote_has_it(
    notes_branch_reached: ScratchRepository,
):
    """
    A file seen viewed is recorded on the notes branch the remote holds.
    """
    git = notes_branch_reached.git
    head = git.commit_at("HEAD")
    checkpoints = ViewedCheckpoints.for_pull_request(
        git, SAMPLE_REPOSITORY, CHECKPOINTED_PULL_REQUEST
    )

    checkpoints.record(head, frozenset({VIEWED}))

    assert isinstance(checkpoints, NotesBranchViewedCheckpoints)
    pushed = GitCommandRunner(notes_branch_reached.notes_remote_path).file_at(
        ScratchBranch.PERSONAL_NOTES, checkpoints.path
    )
    assert ViewedCheckpointFile.from_json(json.loads(pushed)) == ViewedCheckpointFile(
        {VIEWED: head}
    )


def test_checkpoints_on_the_personal_notes_branch_are_read_by_a_later_run(
    notes_branch_reached: ScratchRepository,
):
    """
    A later run reads what an earlier one recorded from the notes branch, not the work
    branch the clone has checked out.
    """
    git = notes_branch_reached.git
    head = git.commit_at("HEAD")
    ViewedCheckpoints.for_pull_request(
        git, SAMPLE_REPOSITORY, CHECKPOINTED_PULL_REQUEST
    ).record(head, frozenset({VIEWED}))

    later = ViewedCheckpoints.for_pull_request(
        git, SAMPLE_REPOSITORY, CHECKPOINTED_PULL_REQUEST
    )

    assert later.read() == {VIEWED: head}


def test_checkpoints_are_kept_in_the_clone_where_no_remote_has_the_notes_branch(
    scratch_repository: ScratchRepository,
):
    """
    Without a reachable notes branch, the files seen viewed are kept in the clone.
    """
    scratch_repository.write(NEVER_VIEWED, "")
    scratch_repository.commit_everything("a commit to record")
    git = scratch_repository.git
    head = git.commit_at("HEAD")
    checkpoints = ViewedCheckpoints.for_pull_request(
        git, SAMPLE_REPOSITORY, CHECKPOINTED_PULL_REQUEST
    )

    checkpoints.record(head, frozenset({VIEWED}))

    assert isinstance(checkpoints, ClonedViewedCheckpoints)
    assert checkpoints.read() == {VIEWED: head}


def test_keeping_checkpoints_in_the_clone_offers_the_notes_setup(
    scratch_repository: ScratchRepository, caplog: pytest.LogCaptureFixture
):
    """
    Without a reachable notes branch, the run says how to set one up.
    """
    ViewedCheckpoints.for_pull_request(
        scratch_repository.git, SAMPLE_REPOSITORY, CHECKPOINTED_PULL_REQUEST
    )

    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
    ]
    assert [
        f"/{SetupPersonalNotesSkill.skill_name}" in message for message in warnings
    ] == [True]

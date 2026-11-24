"""
Triaging each file of a pull request from where the viewer last viewed it, by the viewed
states GitHub lists and the heads files were seen viewed at.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath

from basstler.git.commands import GitCommandRunner
from basstler.github.pull_request_changes import (
    CommitStart,
    ComparisonStart,
    FetchedPullRequest,
    LastReviewStart,
    PullRequestChanges,
    PullRequestChangesReader,
    StartCommit,
    StartReason,
)
from basstler.github.repository import Repository
from basstler.json_model import ValidatedJSONModel
from basstler.locations import ProjectLocation, RepositoryStateLocation
from basstler.personal_notes.branch import (
    NotesBranchWriter,
    NotesFileChanges,
    PersonalNotesBranch,
    PersonalNotesLocation,
)
from basstler.personal_notes.contribution import SetupPersonalNotesSkill
from basstler.review_triage.comparison import FileVerdict
from basstler.review_triage.exceptions import PullRequestHeadMoved
from basstler.review_triage.file_listing import (
    FileListing,
    FileListingReader,
    FileViewedState,
)
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome
from basstler.shell_configuration import FetchedBranchReference
from basstler.standard_streams import StandardStreamHandler
from basstler.text_file import TextFile

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger.
"""

CHECKPOINT_SUFFIX = ".json"
"""
The suffix of the file keeping one pull request's checkpoints.
"""

# %% where files were seen viewed


class ViewedCheckpointFile(ValidatedJSONModel):
    """
    The head commit each file of one pull request was last seen viewed at.
    """

    viewed_at: dict[PurePosixPath, str] = field(default_factory=dict)
    """
    The head commit by each file's path.
    """

    def rendered(self) -> str:
        """
        :return: The file's text.
        """
        return json.dumps(self.to_json(), indent=2)


class ViewedCheckpoints(ABC):
    """
    The heads one pull request's files were last seen viewed at.
    """

    @classmethod
    def for_pull_request(
        cls, git: GitCommandRunner, repository: Repository, number: int
    ) -> ViewedCheckpoints:
        """
        :param git: The clone the triage runs in.
        :param repository: The repository the pull request is opened on.
        :param number: The pull request's number.
        :return: The pull request's checkpoints on the clone's personal-notes branch, or
            in the clone itself where no remote has that branch.
        """
        file_name = PurePosixPath(
            repository.owner, repository.name, f"{number}{CHECKPOINT_SUFFIX}"
        )
        notes_branch = PersonalNotesBranch(
            PersonalNotesLocation.resolve(git.working_directory, os.environ), git
        )
        if notes_branch.fetch_if_present() is None:
            logger.warning(
                "Keeping the files seen viewed in this clone only, as no remote has the "
                f"personal-notes branch {notes_branch.location.branch}; run "
                f"/{SetupPersonalNotesSkill.skill_name} to keep them for every clone "
                "and session"
            )
            directory = git.repository_state_path(
                RepositoryStateLocation.VIEWED_CHECKPOINTS
            )
            return ClonedViewedCheckpoints(directory / file_name)
        return NotesBranchViewedCheckpoints(
            notes_branch, PurePosixPath(ProjectLocation.VIEWED_CHECKPOINTS) / file_name
        )

    @abstractmethod
    def read_file(self) -> ViewedCheckpointFile:
        """
        :return: The checkpoints as last kept; none where none were kept yet.
        """

    @abstractmethod
    def write_file(self, checkpoint_file: ViewedCheckpointFile) -> None:
        """
        :param checkpoint_file: The checkpoints to keep in place of the kept ones.
        """

    def read(self) -> dict[PurePosixPath, str]:
        """
        :return: The head commit each file was last seen viewed at, by its path.
        """
        return self.read_file().viewed_at

    def record(self, head_commit: str, paths: frozenset[PurePosixPath]) -> None:
        """
        :param head_commit: A head commit of the pull request.
        :param paths: Files seen viewed at it.
        """
        if not paths:
            return
        viewed_at = self.read() | dict.fromkeys(paths, head_commit)
        self.write_file(ViewedCheckpointFile(viewed_at))


@dataclass(frozen=True)
class ClonedViewedCheckpoints(ViewedCheckpoints):
    """
    Checkpoints kept in a file of the clone the triage runs in.
    """

    path: Path
    """
    The file.
    """

    def read_file(self) -> ViewedCheckpointFile:
        if not self.path.is_file():
            return ViewedCheckpointFile()
        return ViewedCheckpointFile.from_json(json.loads(TextFile(self.path).read()))

    def write_file(self, checkpoint_file: ViewedCheckpointFile) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        TextFile(self.path).write(checkpoint_file.rendered())


@dataclass(frozen=True)
class NotesBranchViewedCheckpoints(ViewedCheckpoints):
    """
    Checkpoints kept on the personal-notes branch, so every clone and session of the
    viewer resumes from them.
    """

    branch: PersonalNotesBranch
    """
    The notes branch, fetched.
    """

    path: PurePosixPath
    """
    The checkpoint file, relative to the branch's root.
    """

    def read_file(self) -> ViewedCheckpointFile:
        text = self.branch.git.file_at(FetchedBranchReference.PERSONAL_NOTES, self.path)
        if text is None:
            return ViewedCheckpointFile()
        return ViewedCheckpointFile.from_json(json.loads(text))

    def write_file(self, checkpoint_file: ViewedCheckpointFile) -> None:
        """
        :raises NotesBranchMissingError: If no remote has the notes branch any more.
        :raises NotesPushRejectedError: If the remote rejects the push.
        """
        NotesBranchWriter(self.branch).write(
            NotesFileChanges({self.path: checkpoint_file.rendered()}),
            f"Record the files seen viewed in {self.path.as_posix()}",
        )


# %% triaging from the viewed states


@dataclass(frozen=True)
class ViewedStateStart(ComparisonStart):
    """
    Each file from where the viewer last viewed it, its changes read from the merge base
    for :class:`ViewedFilesTriage` to start each file where it was viewed.
    """

    def start_commit(self, fetched: FetchedPullRequest) -> StartCommit:
        return StartCommit(fetched.merge_base, StartReason.VIEWED_FILES)


@dataclass(frozen=True)
class ViewedFilesTriage:
    """
    Triages a pull request leaving out the files the viewer viewed as they are, judging
    one viewed before it last changed from the head it was seen viewed at, and every
    other file from the merge base.
    """

    triager: PullRequestTriager
    """
    How each range of the pull request's changes is triaged.
    """

    reader: PullRequestChangesReader
    """
    Reads the pull request's changes from a start.
    """

    repository: Repository
    """
    The repository the pull request is opened on.
    """

    listing: FileListingReader
    """
    Reads the files GitHub lists, with the viewer's state of each.
    """

    checkpoints: ViewedCheckpoints
    """
    The heads its files were seen viewed at.
    """

    def outcome(self, number: int) -> TriageOutcome:
        """
        :param number: The pull request's number.
        :return: Its triage; from where :class:`LastReviewStart` starts when GitHub
            refuses to list its files.
        :raises PullRequestHeadMoved: If GitHub lists them at another head commit.
        """
        whole = self.reader.read(self.repository, number, ViewedStateStart())
        listed = self.listing.read(whole.pull_request.node_identifier)
        if listed.refusals:
            logger.warning(
                "Triaging from your last review, as GitHub did not list the files "
                f"you viewed: {'; '.join(listed.refusals)}"
            )
            return self.triager.triage(
                self.reader.read(self.repository, number, LastReviewStart())
            )
        listing: FileListing = listed.result
        head_commit = whole.pull_request.head.commit
        if listing.head_commit != head_commit:
            raise PullRequestHeadMoved(number, head_commit, listing.head_commit)
        viewed = listing.paths_in(FileViewedState.VIEWED)
        self.checkpoints.record(head_commit, viewed)
        unviewed = replace(
            whole,
            files=tuple(change for change in whole.files if change.path not in viewed),
        )
        outcome = self.triager.triage(unviewed)
        verdicts: dict[PurePosixPath, FileVerdict] = {
            verdict.change.path: verdict for verdict in outcome.files
        }
        for commit, paths in self.viewed_before_changing(listing, whole).items():
            since = self.triager.triage(
                self.reader.read(self.repository, number, CommitStart(commit))
            )
            verdicts |= {
                verdict.change.path: verdict
                for verdict in since.files
                if verdict.change.path in paths
            }
        return TriageOutcome(
            whole.pull_request,
            outcome.renames,
            tuple(verdicts[change.path] for change in unviewed.files),
            whole.start,
            viewed,
        )

    def viewed_before_changing(
        self, listing: FileListing, whole: PullRequestChanges
    ) -> dict[str, frozenset[PurePosixPath]]:
        """
        :param listing: The files GitHub lists, with the viewer's states.
        :param whole: The pull request's whole change.
        :return: The files viewed before they last changed, by the head commit each was
            seen viewed at, for each such commit the head still contains.
        """
        recorded = self.checkpoints.read()
        git = self.reader.git
        groups: dict[str, set[PurePosixPath]] = {}
        for path in listing.paths_in(FileViewedState.DISMISSED):
            commit = recorded.get(path)
            if commit is not None and git.contains(
                commit, whole.pull_request.head.commit
            ):
                groups.setdefault(commit, set()).add(path)
        return {commit: frozenset(paths) for commit, paths in groups.items()}

"""
A whole pull request triaged: its renames and the verdict on each file it changes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from basstler.github.pull_request_changes import (
    PullRequestChanges,
    RestPullRequest,
    StartCommit,
)
from basstler.review_triage.base_branch_merges import BaseBranchMergeDetection
from basstler.review_triage.commit_tree import CommitModules
from basstler.review_triage.comparison import (
    FileJudgment,
    FileNeedingReview,
    FileTriager,
    FileVerdict,
    JudgmentContext,
    MechanicalChange,
    MechanicalFile,
    EmptyPackageAddition,
    ProseComparison,
    RenamedTextComparison,
)
from basstler.review_triage.declaration import DescriptionDeclaration
from basstler.review_triage.detection import RenameDetection
from basstler.review_triage.definition_moves import (
    DefinitionMoveComparison,
    DefinitionMoveDetection,
)
from basstler.review_triage.file_moves import FileMoveDetection
from basstler.review_triage.module_moves import ModuleMoveDetection
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.review_samples import ReviewSample, ReviewSampling
from basstler.review_triage.subclass_substitutions import SubclassSubstitutionDetection
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.rules import TriageRule
from basstler.review_triage.definitions import DefinitionIndex

# %% the outcome


@dataclass(frozen=True)
class TriageOutcome:
    """
    Which of a pull request's files a reviewer has to read.
    """

    pull_request: RestPullRequest
    """
    The pull request triaged.
    """

    renames: RenameMap
    """
    The renames applied in judging its files.
    """

    files: tuple[FileVerdict, ...]
    """
    The verdict on each file it changes.
    """

    start: StartCommit
    """
    The commit its changes were triaged from, and why.
    """

    samples: tuple[ReviewSample, ...] = ()
    """
    The mechanical files left for review to show a rename.
    """

    @property
    def mechanical_files(self) -> tuple[MechanicalFile, ...]:
        """
        The files a reviewer need not read.
        """
        return tuple(file for file in self.files if isinstance(file, MechanicalFile))

    @property
    def files_needing_review(self) -> tuple[FileNeedingReview, ...]:
        """
        The files a reviewer has to read.
        """
        return tuple(file for file in self.files if isinstance(file, FileNeedingReview))

    @property
    def files_to_mark_viewed(self) -> tuple[MechanicalFile, ...]:
        """
        The mechanical files not left for review as a sample.
        """
        sampled = {sample.path for sample in self.samples}
        return tuple(
            file for file in self.mechanical_files if file.change.path not in sampled
        )


# %% triaging


@dataclass(frozen=True)
class PullRequestTriager:
    """
    Triages a pull request with a configurable set of rename sources and file judgments.
    """

    rename_sources: tuple[RenameSource, ...] = (
        RenameDetection(),
        ModuleMoveDetection(),
        DefinitionMoveDetection(),
        FileMoveDetection(),
        DescriptionDeclaration(),
    )
    """
    The sources of the pull request's renames, a later source outranking an earlier.
    """

    judgments: tuple[FileJudgment, ...] = (
        DefinitionMoveComparison(),
        ProseComparison(),
        EmptyPackageAddition(),
        RenamedTextComparison(),
    )
    """
    The judgments of each file, the first one applying to a file deciding it.
    """

    rules: frozenset[TriageRule] = frozenset()
    """
    The opt-in rules in force.
    """

    sampling: ReviewSampling | None = None
    """
    Picks the mechanical files left for review to show a rename, ``None`` to leave none.
    """

    def renames(self, changes: PullRequestChanges) -> RenameMap:
        """
        :param changes: A pull request and the files it changes.
        :return: The renames its files are judged with.
        """
        return RenameMap.from_decisions(
            source.decisions(changes) for source in self.rename_sources
        )

    def triage(self, changes: PullRequestChanges) -> TriageOutcome:
        """
        :param changes: A pull request and the files it changes.
        :return: The verdict on each of its files, a file only merges of the base branch
            changed mechanical without being judged.
        """
        separated = BaseBranchMergeDetection().separate(changes)
        triager = self.file_triager(separated.own)
        verdicts: dict[PurePosixPath, FileVerdict] = {
            change.path: MechanicalFile(
                change, frozenset({MechanicalChange.BASE_BRANCH_MERGE})
            )
            for change in separated.merged
        } | {change.path: triager.triage(change) for change in separated.own.files}
        renames = triager.context.renames
        files = tuple(verdicts[change.path] for change in changes.files)
        outcome = TriageOutcome(changes.pull_request, renames, files, changes.start)
        if self.sampling is None:
            return outcome
        return replace(outcome, samples=self.sampling.samples(renames, files))

    def file_triager(self, changes: PullRequestChanges) -> FileTriager:
        """
        :param changes: A pull request's own changes, those of base branch merges
            aside.
        :return: What judges each of its files, with its renames, moves and
            substitutions.
        """
        renames = self.renames(changes)
        return FileTriager(
            JudgmentContext(
                renames,
                DefinitionIndex(CommitModules(changes.commits.base_tree)),
                DefinitionMoveDetection().moved_definitions(changes, renames),
                RenameMap.from_decisions(
                    [SubclassSubstitutionDetection().decisions(changes)]
                ),
                self.rules,
            ),
            self.judgments,
        )

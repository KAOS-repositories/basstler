"""
A whole pull request triaged: its renames and the verdict on each file it changes.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from basstler.review_triage.rule_fixes import RuleFixComparison
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
        RuleFixComparison(DefinitionMoveComparison()),
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

    def triage(self, changes: PullRequestChanges) -> TriageOutcome:
        """
        :param changes: A pull request and the files it changes.
        :return: The verdict on each of its files, a file only merges of the base branch
            changed mechanical without being judged.
        """
        separated = BaseBranchMergeDetection().separate(changes)
        own_changes = separated.own
        renames = RenameMap.from_decisions(
            source.decisions(own_changes) for source in self.rename_sources
        )
        base_definitions = DefinitionIndex(CommitModules(own_changes.commits.base_tree))
        triager = FileTriager(
            JudgmentContext(
                renames,
                base_definitions,
                DefinitionMoveDetection().moved_definitions(own_changes, renames),
                RenameMap.from_decisions(
                    [SubclassSubstitutionDetection().decisions(own_changes)]
                ),
                self.rules,
            ),
            self.judgments,
        )
        verdicts: dict[PurePosixPath, FileVerdict] = {
            change.path: MechanicalFile(
                change, frozenset({MechanicalChange.BASE_BRANCH_MERGE})
            )
            for change in separated.merged
        } | {change.path: triager.triage(change) for change in own_changes.files}
        return TriageOutcome(
            changes.pull_request,
            renames,
            tuple(verdicts[change.path] for change in changes.files),
            changes.start,
        )

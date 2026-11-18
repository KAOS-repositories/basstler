"""
A whole pull request triaged: its renames and the verdict on each file it changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from basstler.progress import ProgressStep, ProgressUnit
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
from basstler.review_triage.detection import MemberRenameDetection, RenameDetection
from basstler.review_triage.definition_moves import (
    DefinitionMoveComparison,
    DefinitionMoveDetection,
)
from basstler.review_triage.file_moves import FileMoveDetection
from basstler.review_triage.markdown import MarkdownComparison
from basstler.review_triage.member_renames import MemberRenamer
from basstler.review_triage.referents import MemberResolver
from basstler.review_triage.module_moves import ModuleMoveDetection
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.subclass_substitutions import SubclassSubstitutionDetection
from basstler.review_triage.renames import RenameDecisions, RenameMap
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
        MemberRenameDetection(),
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
        MarkdownComparison(),
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
        context = self.context(own_changes)
        triager = FileTriager(context, self.judgments)
        verdicts: dict[PurePosixPath, FileVerdict] = {
            change.path: MechanicalFile(
                change, frozenset({MechanicalChange.BASE_BRANCH_MERGE})
            )
            for change in separated.merged
        }
        with ProgressStep.JUDGING_FILES.bar(
            len(own_changes.files), ProgressUnit.FILE
        ) as progress:
            for change in own_changes.files:
                verdicts[change.path] = triager.triage(change)
                progress.update()
        return TriageOutcome(
            changes.pull_request,
            context.renames,
            tuple(verdicts[change.path] for change in changes.files),
            changes.start,
        )

    def context(self, changes: PullRequestChanges) -> JudgmentContext:
        """
        :param changes: A pull request's own changes, without merges of its base branch.
        :return: What its files are judged against: the renames every source of
            :attr:`rename_sources` finds in them, and the definitions they move.
        """
        moves = DefinitionMoveDetection()
        substitutions = SubclassSubstitutionDetection()
        decisions: list[RenameDecisions] = []
        with ProgressStep.FINDING_RENAMES_AND_MOVES.bar(
            len((*self.rename_sources, moves, substitutions)), ProgressUnit.DETECTION
        ) as progress:
            for source in self.rename_sources:
                progress.set_postfix_str(source.label)
                decisions.append(source.decisions(changes))
                progress.update()
            renames = RenameMap.from_decisions(decisions)
            progress.set_postfix_str(moves.label)
            moved_definitions = moves.moved_definitions(changes, renames)
            progress.update()
            progress.set_postfix_str(substitutions.label)
            substitution_renames = RenameMap.from_decisions(
                [substitutions.decisions(changes)]
            )
            progress.update()
        base_modules = CommitModules(changes.commits.base_tree)
        return JudgmentContext(
            renames,
            DefinitionIndex(base_modules),
            moved_definitions,
            substitution_renames,
            self.rules,
            MemberRenamer(renames.binding_renames, MemberResolver(base_modules)),
        )

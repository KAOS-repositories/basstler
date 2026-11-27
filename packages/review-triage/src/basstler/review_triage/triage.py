"""
A whole pull request triaged: its renames and the verdict on each file it changes.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from basstler.git.commit_range import FileVersions
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
    FileTriager,
    FileNeedingReview,
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
from basstler.review_triage.plan_replay import PlanReplay, ReplayingFileTriager
from basstler.review_triage.recorded_plans import PlanRecord
from basstler.review_triage.rename_sources import RenameSource
from basstler.review_triage.review_samples import ReviewSample, ReviewSampling
from basstler.review_triage.rule_fixes import RuleFixComparison
from basstler.review_triage.subclass_substitutions import SubclassSubstitutionDetection
from basstler.review_triage.renames import RenameDecisions, RenameMap
from basstler.review_triage.rules import DEFAULT_RULES, TriageRule
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
        RuleFixComparison(DefinitionMoveComparison()),
        MarkdownComparison(),
        ProseComparison(),
        EmptyPackageAddition(),
        RenamedTextComparison(),
    )
    """
    The judgments of each file, the first one applying to a file deciding it.
    """

    rules: frozenset[TriageRule] = DEFAULT_RULES
    """
    The rules in force.
    """

    plan_records: tuple[PlanRecord, ...] = ()
    """
    Plans commits applied beyond those their messages record.
    """

    workers: int | None = None
    """
    The most processes judging files at once, ``None`` for one per processor.
    """

    files_per_worker: int = 25
    """
    The fewest files each process judging them is started for; fewer files are judged in
    this process alone.
    """

    files_per_batch: int = 10
    """
    The files a judging process is handed at a time.
    """

    sampling: ReviewSampling | None = None
    """
    Picks the mechanical files left for review to show a rename, ``None`` to leave none.
    """

    def triage(self, changes: PullRequestChanges) -> TriageOutcome:
        """
        :param changes: A pull request and the files it changes.
        :return: The verdict on each of its files, a file only merges of the base branch
            changed mechanical without being judged, and a file a recorded plan changed
            judged against the plan's replay.
        """
        separated = BaseBranchMergeDetection().separate(changes)
        triager = self.file_triager(separated.own)
        verdicts: dict[PurePosixPath, FileVerdict] = {
            change.path: MechanicalFile(
                change, frozenset({MechanicalChange.BASE_BRANCH_MERGE})
            )
            for change in separated.merged
        }
        verdicts |= self.judged_files(triager, separated.own.files)
        renames = triager.context.renames
        files = tuple(verdicts[change.path] for change in changes.files)
        outcome = TriageOutcome(changes.pull_request, renames, files, changes.start)
        if self.sampling is None:
            return outcome
        return replace(outcome, samples=self.sampling.samples(renames, files))

    def file_triager(self, changes: PullRequestChanges) -> ReplayingFileTriager:
        """
        :param changes: A pull request's own changes, those of base branch merges
            aside.
        :return: What judges each of its files, with its renames, moves and
            substitutions, and the replays of the plans its commits record.
        """
        return ReplayingFileTriager(
            self.context(changes),
            self.judgments,
            PlanReplay.from_records(
                (*PlanRecord.recorded_in(changes.commits), *self.plan_records),
                changes.commits,
            ),
        )

    def judged_files(
        self, triager: FileTriager, changes: tuple[FileVersions, ...]
    ) -> dict[PurePosixPath, FileVerdict]:
        """
        :param triager: What judges each file.
        :param changes: The files to judge.
        :return: The verdict on each file, by its path, judged by up to :attr:`workers`
            processes at once when there are files enough for more than one.
        """
        batches = [
            changes[start : start + self.files_per_batch]
            for start in range(0, len(changes), self.files_per_batch)
        ]
        worker_count = min(
            self.workers or os.cpu_count() or 1,
            len(changes) // self.files_per_worker,
        )
        verdicts: dict[PurePosixPath, FileVerdict] = {}
        with ProgressStep.JUDGING_FILES.bar(
            len(changes), ProgressUnit.FILE
        ) as progress:
            if worker_count <= 1:
                for change in changes:
                    verdicts[change.path] = triager.triage(change)
                    progress.update()
                return verdicts
            with ProcessPoolExecutor(worker_count) as pool:
                judging = [pool.submit(triager.triage_each, batch) for batch in batches]
                for judged in as_completed(judging):
                    for verdict in judged.result():
                        verdicts[verdict.change.path] = verdict
                    progress.update(len(judged.result()))
        return verdicts

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
            base_modules=base_modules,
            head_modules=CommitModules(changes.commits.head_tree),
        )

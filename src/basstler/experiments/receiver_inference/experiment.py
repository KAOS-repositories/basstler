"""
Triages pull requests once per way of inferring receiver classes, and tabulates the
files each way proves mechanical, the time it takes, what it costs to install and where
a type checker disputes basstler's inference.
"""

from __future__ import annotations

import re
import tempfile
from collections import Counter
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import cached_property
from pathlib import Path

from basstler.experiments.measurement import Measurement, Stopwatch, Unit
from basstler.experiments.receiver_inference.cross_check import (
    ReceiverAgreement,
    ReceiverCrossCheck,
)
from basstler.experiments.receiver_inference.exceptions import ReceiversNotProbed
from basstler.experiments.receiver_inference.probes import (
    AnswerRecording,
    FileProbe,
    NoInference,
    ReceiverQuestion,
    RevealedInference,
)
from basstler.experiments.receiver_inference.type_checkers import TypeChecker
from basstler.experiments.results import ResultRow, ResultTable
from basstler.git.commands import GitCommandRunner
from basstler.github.client import GitHubRestClient
from basstler.github.pull_request_changes import (
    MergeBaseStart,
    PullRequestChanges,
    PullRequestChangesReader,
)
from basstler.github.repository import Repository
from basstler.locations import ExperimentLocation
from basstler.review_triage.calls import (
    CALLEE_RESOLUTIONS,
    AnnotationInference,
    InferredReceiverMethod,
    ReceiverInference,
)
from basstler.review_triage.commit_tree import CommitModules
from basstler.review_triage.definition_moves import DefinitionMoveComparison
from basstler.review_triage.definitions import DefinitionIndex
from basstler.review_triage.keyword_arguments import (
    KEYWORD_RULES,
    ArgumentsPassedByKeyword,
    KeywordArgumentComparison,
)
from basstler.review_triage.markdown import MarkdownComparison
from basstler.review_triage.rules import TriageRule
from basstler.review_triage.triage import PullRequestTriager, TriageOutcome

PULL_REQUEST_REFERENCE = re.compile(
    r"(?P<repository>[^#\s]+/[^#\s]+)#(?P<number>\d+)(?::(?P<rules>[\w,-]+))?"
)
"""
A pull request named as ``owner/name#number``, optionally followed by ``:rule,rule``
naming the opt-in triage rules it is triaged with.
"""

NO_INFERENCE = "none"
"""
The name of the triage that infers no receiver class.
"""

OWN_INFERENCE = "basstler"
"""
The name of the triage inferring receivers with :class:`AnnotationInference`.
"""

PYTHON_SUFFIX = ".py"
"""
The suffix of the files a type checker reads.
"""


class ResultName(StrEnum):
    """
    The name of each table the experiment writes.
    """

    OUTCOMES = "receiver-inference"
    """
    What each way of inferring receivers made of each pull request.
    """

    COSTS = "receiver-inference-costs"
    """
    What each way costs to install.
    """

    AGREEMENTS = "receiver-inference-agreements"
    """
    How often each checker's classes agree with basstler's.
    """

    DISPUTES = "receiver-inference-disputes"
    """
    Every receiver whose inferred class a checker disputes.
    """


# %% what is triaged


@dataclass(frozen=True)
class PullRequestCase:
    """
    One pull request the experiment triages, with the opt-in rules it is triaged with.
    """

    repository: Repository
    """
    The repository holding it.
    """

    number: int
    """
    Its number.
    """

    rules: frozenset[TriageRule] = frozenset()
    """
    The opt-in triage rules in force.
    """

    @classmethod
    def parse(cls, reference: str) -> PullRequestCase:
        """
        :param reference: ``owner/name#number``, optionally followed by
            ``:rule,rule``.
        :return: The pull request it names.
        :raises ValueError: If the reference has another shape.
        """
        parsed = PULL_REQUEST_REFERENCE.fullmatch(reference)
        if parsed is None:
            raise ValueError(f"not a pull request reference: {reference}")
        rules = parsed["rules"].split(",") if parsed["rules"] else []
        return cls(
            Repository.parse(parsed["repository"]),
            int(parsed["number"]),
            frozenset(map(TriageRule, rules)),
        )

    def __str__(self) -> str:
        """
        :return: The pull request as ``owner/name#number``.
        """
        return f"{self.repository.owner}/{self.repository.name}#{self.number}"


# %% the rows


@dataclass(frozen=True)
class InferenceOutcome(ResultRow):
    """
    What one way of inferring receivers made of one pull request.
    """

    pull_request: str
    """
    The pull request triaged, as ``owner/name#number``.
    """

    inference: str
    """
    The way receivers were inferred.
    """

    files: int
    """
    The files the pull request changes.
    """

    receivers: int
    """
    The method call receivers the triage asked the class of.
    """

    receivers_inferred: int
    """
    Those inferred to be of a class the base commit defines.
    """

    receivers_probed: int | None
    """
    The receivers a type checker was asked for, ``None`` without a checker.
    """

    needing_review: int
    """
    The files left for a reviewer to read.
    """

    newly_mechanical: int
    """
    The files proved mechanical that the triage without inference left for review.
    """

    newly_needing_review: int
    """
    The files left for review that the triage without inference proved mechanical.
    """

    mechanical_beyond_basstler: int
    """
    The files proved mechanical that basstler's inference left for review.
    """

    needing_review_beyond_basstler: int
    """
    The files left for review that basstler's inference proved mechanical.
    """

    seconds: Measurement
    """
    The time of the whole triage, any checker's run included.
    """

    checker_seconds: Measurement | None
    """
    The time of the type checker's run alone, ``None`` without a checker.
    """


@dataclass(frozen=True)
class InferenceCost(ResultRow):
    """
    What one way of inferring receivers costs to install.
    """

    inference: str
    """
    The way receivers are inferred.
    """

    version: str
    """
    The version installed.
    """

    install_megabytes: float | None
    """
    The disk space it takes beyond basstler's own, ``None`` for basstler's inference,
    which is part of basstler.
    """

    dependencies: int
    """
    How many distributions it installs besides itself.
    """

    dependency_names: str
    """
    Their names.
    """


@dataclass(frozen=True)
class AgreementCount(ResultRow):
    """
    How many receivers of one pull request a checker answered in one relation to
    basstler's answer.
    """

    pull_request: str
    """
    The pull request triaged, as ``owner/name#number``.
    """

    checker: str
    """
    The type checker compared with basstler.
    """

    agreement: ReceiverAgreement
    """
    How the two answers relate.
    """

    receivers: int
    """
    The receivers answered so.
    """


@dataclass(frozen=True)
class DisputedReceiver(ResultRow):
    """
    A receiver whose class basstler inferred and a checker disputes.
    """

    pull_request: str
    """
    The pull request triaged, as ``owner/name#number``.
    """

    checker: str
    """
    The type checker disputing it.
    """

    path: str
    """
    The file holding it in the base commit.
    """

    line: int
    """
    The line it starts on, counted from one.
    """

    receiver: str
    """
    Its source.
    """

    inferred_class: str
    """
    The class basstler inferred.
    """

    revealed_class: str
    """
    The class the checker revealed.
    """

    agreement: ReceiverAgreement
    """
    How the two classes relate.
    """


# %% one pull request's triages


@dataclass(frozen=True)
class InferringTriage:
    """
    The default triage, inferring receiver classes one given way.
    """

    inference: ReceiverInference
    """
    The way receivers are inferred.
    """

    def keyword_comparison(self) -> KeywordArgumentComparison:
        """
        :return: The default comparison of Python files, with the inference.
        """
        resolutions = tuple(
            InferredReceiverMethod(self.inference)
            if isinstance(resolution, InferredReceiverMethod)
            else resolution
            for resolution in CALLEE_RESOLUTIONS
        )
        return KeywordArgumentComparison(
            rules=tuple(
                ArgumentsPassedByKeyword(resolutions)
                if isinstance(rule, ArgumentsPassedByKeyword)
                else rule
                for rule in KEYWORD_RULES
            )
        )

    def triager(self, rules: frozenset[TriageRule]) -> PullRequestTriager:
        """
        :param rules: The opt-in rules in force.
        :return: The default triager, comparing Python with the inference.
        """
        keyword = self.keyword_comparison()
        default = PullRequestTriager()
        return replace(
            default,
            judgments=tuple(
                DefinitionMoveComparison(keyword)
                if isinstance(judgment, DefinitionMoveComparison)
                else MarkdownComparison(keyword)
                if isinstance(judgment, MarkdownComparison)
                else judgment
                for judgment in default.judgments
            ),
            rules=rules,
        )


@dataclass(frozen=True)
class TriageRun:
    """
    One triage of a pull request, and how long it took.
    """

    outcome: TriageOutcome
    """
    The verdict on each file.
    """

    seconds: float
    """
    The time of the whole triage, any checker's run included.
    """

    receivers: int
    """
    The method call receivers the triage asked the class of.
    """

    answers: dict[ReceiverQuestion, str]
    """
    The class each receiver was answered with that the base commit defines.
    """

    checker_seconds: float | None = None
    """
    The time of the type checker's run alone, ``None`` without a checker.
    """

    receivers_probed: int | None = None
    """
    The receivers the type checker was asked for, ``None`` without a checker.
    """

    @property
    def needing_review(self) -> frozenset[str]:
        """
        The paths of the files left for review.
        """
        return frozenset(
            str(file.change.path) for file in self.outcome.files_needing_review
        )


@dataclass(frozen=True)
class RevealedAnswers:
    """
    What one type checker revealed about the receivers of one pull request.
    """

    answers: dict[ReceiverQuestion, str]
    """
    The class revealed for each receiver revealed as an instance of one.
    """

    receivers_probed: int
    """
    The receivers the checker was asked for.
    """

    seconds: float
    """
    The time of probing the files, running the checker and restoring them.
    """

    checker_seconds: float
    """
    The time of the checker's run alone.
    """


@dataclass(frozen=True)
class PullRequestTriages:
    """
    The triages of one pull request, one per way of inferring receivers.
    """

    case: PullRequestCase
    """
    The pull request.
    """

    changes: PullRequestChanges
    """
    Its files, in both versions.
    """

    base_checkout: Path
    """
    A worktree of its base commit, which the checkers read.
    """

    source_roots: tuple[str, ...]
    """
    The glob patterns, relative to a checkout, of the directories imports resolve in.
    """

    def triage(self, recording: AnswerRecording) -> TriageRun:
        """
        :param recording: The way receivers are inferred, recording its answers.
        :return: The pull request triaged with it.
        """
        triager = InferringTriage(recording).triager(self.case.rules)
        with Stopwatch() as stopwatch:
            outcome = triager.triage(self.changes)
        return TriageRun(
            outcome, stopwatch.seconds, len(recording.asked), dict(recording.answers)
        )

    @cached_property
    def base_paths(self) -> dict[str, str]:
        """
        The path, relative to the checkout, of each changed Python file by its base
        text.
        """
        return {
            file.base_text: (file.previous_path or file.path).as_posix()
            for file in self.changes.files
            if file.base_text is not None
            and (file.previous_path or file.path).suffix == PYTHON_SUFFIX
        }

    @cached_property
    def receivers(self) -> frozenset[ReceiverQuestion]:
        """
        The receiver of every method call in the changed Python files' base versions,
        every receiver a triage asks about among them.
        """
        return frozenset(
            question
            for module in self.base_paths
            for question in ReceiverQuestion.from_method_calls(module)
        )

    @cached_property
    def base_definitions(self) -> DefinitionIndex:
        """
        The definitions of the base commit.
        """
        return DefinitionIndex(CommitModules(self.changes.commits.base_tree))

    def restore(self, paths: list[str]) -> None:
        """
        Check the files out of the base commit again, undoing any probe written over
        them, a probe left by an interrupted run included.

        :param paths: Files relative to the base checkout.
        """
        if paths:
            GitCommandRunner(self.base_checkout).run("checkout", "--", *paths)

    def reveal(self, checker: TypeChecker) -> RevealedAnswers:
        """
        :param checker: A type checker.
        :return: The classes it reveals for every receiver of the files it checks,
            asked for in one run before any triage.
        """
        with Stopwatch() as whole:
            probes = {
                module: FileProbe.of(
                    path,
                    module,
                    sorted(
                        question.span
                        for question in self.receivers
                        if question.module == module
                    ),
                )
                for module, path in self.base_paths.items()
                if checker.checks(path, self.base_checkout)
            }
            probed = sorted(probe.path for probe in probes.values())
            self.restore(probed)
            for probe in probes.values():
                (self.base_checkout / probe.path).write_text(
                    probe.text, encoding="utf-8", newline=""
                )
            search_paths = [
                path
                for pattern in self.source_roots
                for path in sorted(self.base_checkout.glob(pattern))
                if path.is_dir()
            ]
            with tempfile.TemporaryDirectory() as workspace, Stopwatch() as running:
                revealed = (
                    checker.reveal(
                        probed, search_paths, self.base_checkout, Path(workspace)
                    )
                    if probed
                    else []
                )
            self.restore(probed)
            answers = {
                question: class_name
                for module, probe in probes.items()
                for question, class_name in probe.answers(module, revealed).items()
            }
        return RevealedAnswers(
            answers,
            sum(len(probe.arguments) for probe in probes.values()),
            whole.seconds,
            running.seconds,
        )

    def checked(self, checker: TypeChecker) -> TriageRun:
        """
        :param checker: The type checker asked for the receivers' classes.
        :return: The pull request triaged with the classes the checker revealed, its
            time the checker's run and the triage's together.
        :raises ReceiversNotProbed: If the triage asked about a receiver of a Python
            file the checker was not asked for.
        """
        revealed = self.reveal(checker)
        recording = AnswerRecording(RevealedInference(revealed.answers))
        run = self.triage(recording)
        unprobed = {
            question
            for question in recording.asked
            if question.module in self.base_paths
        } - self.receivers
        if unprobed:
            raise ReceiversNotProbed(
                str(self.case),
                tuple(
                    f"{self.base_paths[question.module]}:{question.span.line}: "
                    f"{question.span.source_in(question.module)}"
                    for question in unprobed
                ),
            )
        return replace(
            run,
            seconds=revealed.seconds + run.seconds,
            checker_seconds=revealed.checker_seconds,
            receivers_probed=revealed.receivers_probed,
        )

    def cross_check(
        self, inferred: TriageRun, revealed: TriageRun
    ) -> ReceiverCrossCheck:
        """
        :param inferred: The triage with basstler's inference.
        :param revealed: The triage with a checker's answers.
        :return: The receivers of the changed Python files either answered.
        """

        def in_python_files(
            answers: dict[ReceiverQuestion, str],
        ) -> dict[ReceiverQuestion, str]:
            return {
                question: class_name
                for question, class_name in answers.items()
                if question.module in self.base_paths
            }

        return ReceiverCrossCheck(
            in_python_files(inferred.answers),
            in_python_files(revealed.answers),
            self.base_definitions,
        )


# %% the experiment


@dataclass(frozen=True)
class CaseResults:
    """
    The rows one pull request contributes to each table.
    """

    outcomes: tuple[InferenceOutcome, ...]
    """
    One row per way of inferring receivers.
    """

    agreements: tuple[AgreementCount, ...] = ()
    """
    How often each checker agrees with basstler, empty without a cross-check.
    """

    disputes: tuple[DisputedReceiver, ...] = ()
    """
    Every receiver whose inferred class a checker disputes.
    """


@dataclass(frozen=True)
class ReceiverInferenceExperiment:
    """
    Compares basstler's receiver inference with type checkers on real pull requests.
    """

    checkout: Path
    """
    A clone of the repositories the pull requests belong to, holding their commits.
    """

    cases: tuple[PullRequestCase, ...]
    """
    The pull requests triaged.
    """

    checkers: tuple[TypeChecker, ...]
    """
    The type checkers compared.
    """

    repetitions: int = 2
    """
    How often each triage is timed.
    """

    cross_check: bool = True
    """
    Whether every receiver basstler infers is compared with what each checker reveals.
    """

    source_roots: tuple[str, ...] = ("src", "*/src")
    """
    The glob patterns, relative to a checkout, of the directories imports resolve in.
    """

    checkouts: Path = ExperimentLocation.CHECKOUTS
    """
    Where the worktrees of the base commits are kept.
    """

    def base_checkout(self, changes: PullRequestChanges) -> Path:
        """
        :param changes: A pull request's changes.
        :return: A worktree of its base commit, added unless it exists.
        """
        base = changes.commits.base_commit
        worktree = self.checkouts / base[:12]
        if not worktree.exists():
            GitCommandRunner(self.checkout).run(
                "worktree", "add", "--detach", str(worktree), base
            )
        return worktree

    def triages(self, case: PullRequestCase) -> PullRequestTriages:
        """
        :param case: A pull request.
        :return: Its changes, ready to be triaged.
        """
        changes = PullRequestChangesReader(
            GitCommandRunner(self.checkout), GitHubRestClient()
        ).read(case.repository, case.number, MergeBaseStart())
        return PullRequestTriages(
            case, changes, self.base_checkout(changes), self.source_roots
        )

    def results(self, case: PullRequestCase) -> CaseResults:
        """
        :param case: A pull request.
        :return: Its rows of every table, its first repetition's triages compared.
        """
        triages = self.triages(case)
        runs: dict[str, list[TriageRun]] = {}
        for _ in range(self.repetitions):
            runs.setdefault(NO_INFERENCE, []).append(
                triages.triage(AnswerRecording(NoInference()))
            )
            runs.setdefault(OWN_INFERENCE, []).append(
                triages.triage(AnswerRecording(AnnotationInference()))
            )
            for checker in self.checkers:
                runs.setdefault(checker.name, []).append(triages.checked(checker))
        outcomes = tuple(
            self.outcome(case, name, timed, runs) for name, timed in runs.items()
        )
        if not self.cross_check:
            return CaseResults(outcomes)
        compared = {
            checker.name: triages.cross_check(
                runs[OWN_INFERENCE][0], runs[checker.name][0]
            ).compare_all()
            for checker in self.checkers
        }
        return CaseResults(
            outcomes,
            tuple(
                AgreementCount(str(case), name, agreement, counted[agreement])
                for name, agreements in compared.items()
                for counted in (Counter(agreements.values()),)
                for agreement in ReceiverAgreement
            ),
            tuple(
                DisputedReceiver(
                    str(case),
                    name,
                    triages.base_paths[question.module],
                    question.span.line,
                    question.span.source_in(question.module),
                    runs[OWN_INFERENCE][0].answers[question],
                    runs[name][0].answers[question],
                    agreement,
                )
                for name, agreements in compared.items()
                for question, agreement in sorted(
                    agreements.items(),
                    key=lambda item: (
                        triages.base_paths[item[0].module],
                        item[0].span,
                    ),
                )
                if agreement.disputes_inference
            ),
        )

    @staticmethod
    def outcome(
        case: PullRequestCase,
        name: str,
        timed: list[TriageRun],
        runs: dict[str, list[TriageRun]],
    ) -> InferenceOutcome:
        """
        :param case: A pull request.
        :param name: One way of inferring receivers.
        :param timed: Its triages of the pull request, one per repetition.
        :param runs: Every way's triages, to compare its verdicts with.
        :return: Its row, its first repetition's verdicts compared.
        """
        first = timed[0]
        checker_seconds = [
            run.checker_seconds for run in timed if run.checker_seconds is not None
        ]
        unaided = runs[NO_INFERENCE][0].needing_review
        own = runs[OWN_INFERENCE][0].needing_review
        return InferenceOutcome(
            pull_request=str(case),
            inference=name,
            files=len(first.outcome.files),
            receivers=first.receivers,
            receivers_inferred=len(first.answers),
            receivers_probed=first.receivers_probed,
            needing_review=len(first.needing_review),
            newly_mechanical=len(unaided - first.needing_review),
            newly_needing_review=len(first.needing_review - unaided),
            mechanical_beyond_basstler=len(own - first.needing_review),
            needing_review_beyond_basstler=len(first.needing_review - own),
            seconds=Measurement.from_samples(
                [run.seconds for run in timed], Unit.SECONDS
            ),
            checker_seconds=(
                Measurement.from_samples(checker_seconds, Unit.SECONDS)
                if checker_seconds
                else None
            ),
        )

    def costs(self) -> list[InferenceCost]:
        """
        :return: What each checker costs to install, after basstler's own inference,
            which costs nothing beyond basstler.
        """
        own = InferenceCost(OWN_INFERENCE, "part of basstler", None, 0, "")
        installed = [
            (checker.name, checker.installation.footprint())
            for checker in self.checkers
        ]
        return [
            own,
            *(
                InferenceCost(
                    name,
                    footprint.version,
                    footprint.megabytes,
                    len(footprint.dependencies),
                    ", ".join(footprint.dependencies),
                )
                for name, footprint in installed
            ),
        ]

    def run(self) -> dict[ResultName, ResultTable]:
        """
        Install the checkers, then triage every pull request with every way.

        :return: Each table, the cross-check's only when it is made.
        """
        for checker in self.checkers:
            checker.installation.install()
        results = [self.results(case) for case in self.cases]
        tables = {
            ResultName.OUTCOMES: ResultTable(
                InferenceOutcome,
                tuple(row for result in results for row in result.outcomes),
            ),
            ResultName.COSTS: ResultTable(InferenceCost, tuple(self.costs())),
        }
        if not self.cross_check:
            return tables
        return tables | {
            ResultName.AGREEMENTS: ResultTable(
                AgreementCount,
                tuple(row for result in results for row in result.agreements),
            ),
            ResultName.DISPUTES: ResultTable(
                DisputedReceiver,
                tuple(row for result in results for row in result.disputes),
            ),
        }

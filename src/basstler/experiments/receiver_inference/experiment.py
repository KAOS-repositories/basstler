"""
Triages pull requests once per way of inferring receiver classes, and tabulates the
files each way proves mechanical, the time it takes and what it costs to install.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from basstler.experiments.measurement import Measurement, Stopwatch, Unit
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
from basstler.review_triage.definition_moves import DefinitionMoveComparison
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

    receivers_inferred: int
    """
    Those inferred to be of a class the base commit defines.
    """

    checker_seconds: float | None = None
    """
    The time of the type checker's run alone, ``None`` without a checker.
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
            outcome, stopwatch.seconds, len(recording.asked), len(recording.answered)
        )

    @property
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

    def restore(self, paths: list[str]) -> None:
        """
        Check the files out of the base commit again, undoing any probe written over
        them, a probe left by an interrupted run included.

        :param paths: Files relative to the base checkout.
        """
        if paths:
            GitCommandRunner(self.base_checkout).run("checkout", "--", *paths)

    def checked(
        self, checker: TypeChecker, questions: set[ReceiverQuestion], recording: float
    ) -> TriageRun:
        """
        :param checker: The type checker asked for the receivers' classes.
        :param questions: The receivers the triage asks about.
        :param recording: The time the triage recording them took.
        :return: The pull request triaged with the classes the checker revealed.
        """
        paths = {
            module: path
            for module, path in self.base_paths.items()
            if checker.checks(path, self.base_checkout)
        }
        probes = {
            module: FileProbe.of(
                paths[module],
                module,
                sorted(
                    question.span for question in questions if question.module == module
                ),
            )
            for module in {question.module for question in questions}
            if module in paths
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
        with tempfile.TemporaryDirectory() as workspace, Stopwatch() as stopwatch:
            revealed = (
                checker.reveal(
                    probed, search_paths, self.base_checkout, Path(workspace)
                )
                if probes
                else []
            )
        self.restore(probed)
        answers = {
            question: class_name
            for module, probe in probes.items()
            for question, class_name in probe.answers(module, revealed).items()
        }
        run = self.triage(AnswerRecording(RevealedInference(answers)))
        return replace(
            run,
            seconds=recording + stopwatch.seconds + run.seconds,
            checker_seconds=stopwatch.seconds,
        )


# %% the experiment


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

    def outcomes(self, case: PullRequestCase) -> list[InferenceOutcome]:
        """
        :param case: A pull request.
        :return: One row per way of inferring receivers.
        """
        triages = self.triages(case)
        runs: dict[str, list[TriageRun]] = {}
        for _ in range(self.repetitions):
            recording = AnswerRecording(NoInference())
            unaided = triages.triage(recording)
            runs.setdefault(NO_INFERENCE, []).append(unaided)
            runs.setdefault(OWN_INFERENCE, []).append(
                triages.triage(AnswerRecording(AnnotationInference()))
            )
            for checker in self.checkers:
                runs.setdefault(checker.name, []).append(
                    triages.checked(checker, recording.asked, unaided.seconds)
                )
        unaided = runs[NO_INFERENCE][0].needing_review
        own = runs[OWN_INFERENCE][0].needing_review
        return [
            InferenceOutcome(
                pull_request=str(case),
                inference=name,
                files=len(timed[0].outcome.files),
                receivers=timed[0].receivers,
                receivers_inferred=timed[0].receivers_inferred,
                needing_review=len(timed[0].needing_review),
                newly_mechanical=len(unaided - timed[0].needing_review),
                newly_needing_review=len(timed[0].needing_review - unaided),
                mechanical_beyond_basstler=len(own - timed[0].needing_review),
                needing_review_beyond_basstler=len(timed[0].needing_review - own),
                seconds=Measurement.from_samples(
                    [run.seconds for run in timed], Unit.SECONDS
                ),
                checker_seconds=(
                    None
                    if timed[0].checker_seconds is None
                    else Measurement.from_samples(
                        [run.checker_seconds for run in timed], Unit.SECONDS
                    )
                ),
            )
            for name, timed in runs.items()
        ]

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

    def run(self) -> tuple[ResultTable, ResultTable]:
        """
        Install the checkers, then triage every pull request with every way.

        :return: The outcome of each triage, and what each way costs to install.
        """
        for checker in self.checkers:
            checker.installation.install()
        outcomes = [row for case in self.cases for row in self.outcomes(case)]
        return ResultTable(tuple(outcomes)), ResultTable(tuple(self.costs()))

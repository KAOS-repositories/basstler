"""
Tests for the receiver inference experiment: reading what type checkers reveal, probing
files for it and answering the triage's questions with it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from basstler.experiments.receiver_inference.cross_check import (
    ReceiverAgreement,
    ReceiverCrossCheck,
)
from basstler.experiments.receiver_inference.experiment import (
    InferringTriage,
    PullRequestCase,
)
from basstler.command_run import CommandRun
from basstler.experiments.receiver_inference.probes import (
    AnswerRecording,
    NoInference,
)
from basstler.experiments.receiver_inference.type_checkers import (
    InstalledPyrefly,
    InstalledTypeChecker,
    Mypy,
    Pyright,
)
from basstler.experiments.tool_installation import ToolInstallation
from basstler.github.repository import Repository
from basstler.review_triage.calls import (
    CallScope,
    CombinedInference,
    ReceiverInference,
)
from basstler.review_triage.comparison import (
    FileTriager,
    FileVerdict,
    JudgmentContext,
    MechanicalFile,
)
from basstler.review_triage.definitions import DefinitionIndex, SourceDefinitions
from basstler.review_triage.keyword_arguments import KeywordChange
from basstler.review_triage.receiver_probes import (
    REVEAL_FUNCTION,
    ExpressionSpan,
    FileProbe,
    ReceiverQuestion,
)
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.rules import TriageRule
from basstler.review_triage.signatures import SignatureReader
from basstler.review_triage.type_checkers import RevealedType, SourcePosition
from tests.constants.paths import DatasetLocation
from tests.review_triage.samples import FileSample

PROBED_PATH = "pkg/use.py"
"""
The file the recorded checker reports reveal types in.
"""

CHECKOUT_PLACEHOLDER = "CHECKOUT"
"""
What the recorded pyright report holds in place of the checkout's absolute path.
"""

# %% revealed types


@pytest.mark.parametrize(
    ("text", "class_name"),
    [
        ("pkg.model.Plotter", "Plotter"),
        ("Plotter | None", "Plotter"),
        ("Plotter*", "Plotter"),
        ("list[pkg.model.Plotter] | None", "list"),
        ("Plotter | Recorder", None),
        ("type[Plotter]", None),
        ("def () -> pkg.model.Plotter", None),
        ("(name: str) -> None", None),
        ("Any", None),
        ("Literal[Outcome.SUCCEEDED]", "Outcome"),
        ("Literal[pkg.model.Outcome.SUCCEEDED, pkg.model.Outcome.ABORTED]", "Outcome"),
        ("Literal[Outcome.SUCCEEDED, Plotter.LINE]", None),
        ("Literal['pkg.model']", None),
        ("Literal[3]", None),
    ],
)
def test_a_revealed_type_names_the_one_class_it_is_an_instance_of(
    text: str, class_name: str | None
):
    """
    A revealed type names a class only for an instance of one class, ``None`` aside.
    """
    position = SourcePosition(PROBED_PATH, 1, 0)

    assert RevealedType(position, text).instance_class == class_name


@pytest.mark.parametrize(
    ("checker", "report", "revealed"),
    [
        (
            Mypy,
            "mypy-report.jsonl",
            [
                RevealedType(SourcePosition(PROBED_PATH, 5, 20), "pkg.model.Plotter"),
                RevealedType(
                    SourcePosition(PROBED_PATH, 8, 16),
                    "list[pkg.model.Plotter] | None",
                ),
            ],
        ),
        (
            Pyright,
            "pyright-report.json",
            [
                RevealedType(SourcePosition(PROBED_PATH, 5, 20), "Plotter"),
                RevealedType(SourcePosition(PROBED_PATH, 9, 16), "type[Plotter]"),
            ],
        ),
        (
            InstalledPyrefly,
            "pyrefly-report.json",
            [RevealedType(SourcePosition(PROBED_PATH, 5, 20), "Plotter")],
        ),
    ],
)
def test_each_checker_reports_the_types_it_revealed_at_their_arguments(
    checker: type[InstalledTypeChecker],
    report: str,
    revealed: list[RevealedType],
    tmp_path: Path,
):
    """
    Every checker's report is read into the revealed types alone, each at the line,
    counted from one, and column, counted from zero, of the expression revealed.
    """
    output = (DatasetLocation.RECEIVER_INFERENCE / report).read_text(encoding="utf-8")
    output = output.replace(CHECKOUT_PLACEHOLDER, tmp_path.as_posix())
    run = CommandRun((), output, "", 1)

    found = checker(ToolInstallation(checker.__name__, tmp_path)).revealed_types(
        run, tmp_path
    )

    assert found == revealed


# %% probes

RECEIVERS = DatasetLocation.RECEIVER_INFERENCE / "receivers.py"
"""
A file whose receivers a probe wraps, two of them starting at one place.
"""


def receiver_spans(text: str) -> list[ExpressionSpan]:
    """
    :param text: A Python file.
    :return: The span of the receiver of every method call in it.
    """
    return sorted(
        question.span for question in ReceiverQuestion.from_method_calls(text)
    )


def test_the_receivers_of_a_file_are_those_of_its_method_calls():
    """
    Every expression a method is called on is a receiver, nested ones included, and its
    span covers its source exactly.
    """
    text = RECEIVERS.read_text(encoding="utf-8")

    found = {span.source_in(text) for span in receiver_spans(text)}

    assert found == {
        ast.get_source_segment(text, node.func.value)
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_a_file_that_does_not_parse_has_no_receivers():
    """
    A file that is not valid Python has no receiver to probe.
    """
    assert ReceiverQuestion.from_method_calls("def broken(:\n") == frozenset()


def test_a_probe_wraps_each_receiver_where_it_is():
    """
    Every receiver is wrapped in ``reveal_type``, an outer one around an inner one
    starting at the same place, columns counted in characters.
    """
    text = RECEIVERS.read_text(encoding="utf-8")

    probe = FileProbe.of(PROBED_PATH, text, receiver_spans(text))

    expected = DatasetLocation.RECEIVER_INFERENCE / "receivers-probed.py"
    assert probe.text == expected.read_text(encoding="utf-8")


def test_a_probe_finds_each_receiver_at_its_argument():
    """
    The argument of each ``reveal_type`` the probe inserts leads back to its receiver.
    """
    text = RECEIVERS.read_text(encoding="utf-8")
    spans = receiver_spans(text)

    probe = FileProbe.of(PROBED_PATH, text, spans)

    inserted = revealed_arguments(probe.text) - revealed_arguments(text)
    assert (set(probe.arguments), set(probe.arguments.values())) == (
        inserted,
        set(spans),
    )


def revealed_arguments(text: str) -> set[SourcePosition]:
    """
    :param text: A Python file.
    :return: Where the argument of each ``reveal_type`` call in it starts.
    """
    return {
        SourcePosition(PROBED_PATH, node.args[0].lineno, node.args[0].col_offset)
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == REVEAL_FUNCTION
    }


def test_revealed_types_answer_the_receivers_revealed_as_one_class():
    """
    A receiver revealed as an instance of one class is answered with that class; one
    revealed otherwise is not answered.
    """
    text = RECEIVERS.read_text(encoding="utf-8")
    probe = FileProbe.of(PROBED_PATH, text, receiver_spans(text))
    [instance, union] = sorted(probe.arguments)[:2]

    answers = probe.answers(
        text,
        [
            RevealedType(instance, "pkg.model.Registry"),
            RevealedType(union, "Plotter | Recorder"),
        ],
    )

    assert answers == {
        ReceiverQuestion(text, probe.arguments[instance]): "Registry",
    }


# %% the triage's questions


@dataclass(frozen=True)
class AnswersGivenInAdvance(ReceiverInference):
    """
    Answers each receiver of a file with the class given for it beforehand.
    """

    answers: dict[ReceiverQuestion, str]
    """
    The class given for each receiver.
    """

    def receiver_class(
        self,
        receiver: ast.expr,
        scope: CallScope,
        reader: SignatureReader,
        renames: RenameMap,
    ) -> str | None:
        if scope.module is None:
            return None
        span = ExpressionSpan.of(receiver, scope.module.text)
        return self.answers.get(ReceiverQuestion(scope.module.text, span))


def triaged_with(sample: FileSample, recording: AnswerRecording) -> FileVerdict:
    """
    :param sample: A file in two versions.
    :param recording: The way receivers are inferred, recording its answers.
    :return: The sample's verdict, its base version's definitions as the commit's.
    """
    triager = FileTriager(
        JudgmentContext(RenameMap(), sample.base_definitions()),
        (InferringTriage(recording).keyword_comparison(),),
    )
    return triager.triage(sample.change())


def test_the_triage_is_answered_the_receivers_it_asked_about():
    """
    The receivers a triage asks about, answered with a class the commit defines, are
    recorded answered and prove the file mechanical.
    """
    sample = FileSample.RECEIVER_TYPE_UNKNOWN
    unanswered = AnswerRecording(NoInference())
    triaged_with(sample, unanswered)
    answers = dict.fromkeys(unanswered.asked, "TrajectoryPlotter")
    answering = AnswerRecording(AnswersGivenInAdvance(answers))

    verdict = triaged_with(sample, answering)

    assert verdict == MechanicalFile(
        sample.change(), frozenset({KeywordChange.KEYWORD_ARGUMENTS})
    )
    assert (unanswered.answers, answering.answers) == ({}, answers)


def asked_receivers(sample: FileSample) -> set[ReceiverQuestion]:
    """
    :param sample: A file in two versions.
    :return: The receivers its triage asks about.
    """
    unanswered = AnswerRecording(NoInference())
    triaged_with(sample, unanswered)
    return unanswered.asked


def test_combined_inferences_answer_what_the_first_leaves_open():
    """
    A receiver the first inference leaves unanswered is answered by the next one.
    """
    sample = FileSample.RECEIVER_TYPE_UNKNOWN
    answers = dict.fromkeys(asked_receivers(sample), "TrajectoryPlotter")
    answering = AnswerRecording(
        CombinedInference((NoInference(), AnswersGivenInAdvance(answers)))
    )

    triaged_with(sample, answering)

    assert answering.answers == answers


def test_combined_inferences_keep_the_first_answer():
    """
    A receiver the first inference answers keeps that answer, whatever a later one says.
    """
    sample = FileSample.RECEIVER_TYPE_UNKNOWN
    asked = asked_receivers(sample)
    first = dict.fromkeys(asked, "TrajectoryPlotter")
    answering = AnswerRecording(
        CombinedInference(
            (
                AnswersGivenInAdvance(first),
                AnswersGivenInAdvance(dict.fromkeys(asked, "Map")),
            )
        )
    )

    triaged_with(sample, answering)

    assert answering.answers == first


@pytest.mark.parametrize(
    "sample",
    [
        FileSample.RECEIVER_TYPE_AMBIGUOUS,
        FileSample.RECEIVER_TYPE_FOLLOWED,
        FileSample.RECEIVER_TYPE_INFERRED,
        FileSample.RECEIVER_TYPE_UNKNOWN,
    ],
)
def test_every_receiver_the_triage_asks_about_is_probed(sample: FileSample):
    """
    The receivers of a file's method calls, probed before any triage, hold every
    receiver the triage then asks about, so one checker run answers them all.
    """
    recording = AnswerRecording(NoInference())
    triaged_with(sample, recording)

    probed = ReceiverQuestion.from_method_calls(sample.change().base_text)

    assert recording.asked
    assert recording.asked <= probed


# %% the cross-check

CLASS_HIERARCHY = DatasetLocation.RECEIVER_INFERENCE / "class-hierarchy.py"
"""
A base class, its subclass and an unrelated class.
"""


@pytest.mark.parametrize(
    ("inferred", "revealed", "agreement"),
    [
        ("Shape", "Shape", ReceiverAgreement.SAME_CLASS),
        ("Shape", "Circle", ReceiverAgreement.SUBCLASS_REVEALED),
        ("Circle", "Shape", ReceiverAgreement.BASE_CLASS_REVEALED),
        ("Shape", "Colour", ReceiverAgreement.UNRELATED_CLASSES),
        ("Shape", None, ReceiverAgreement.INFERRED_ONLY),
        (None, "Shape", ReceiverAgreement.REVEALED_ONLY),
    ],
)
def test_a_cross_check_compares_the_inferred_class_with_the_revealed_one(
    inferred: str | None, revealed: str | None, agreement: ReceiverAgreement
):
    """
    A receiver's inferred and revealed classes agree, one is a subclass of the other,
    they are unrelated, or only one way answers it.
    """
    question = ReceiverQuestion("receiver.method()", ExpressionSpan(1, 0, 1, 8))
    cross_check = ReceiverCrossCheck(
        {question: inferred} if inferred else {},
        {question: revealed} if revealed else {},
        DefinitionIndex(
            SourceDefinitions((CLASS_HIERARCHY.read_text(encoding="utf-8"),))
        ),
    )

    assert cross_check.compare_all() == {question: agreement}


@pytest.mark.parametrize("agreement", [agreement for agreement in ReceiverAgreement])
def test_only_a_revealed_class_unlike_the_inferred_one_disputes_it(
    agreement: ReceiverAgreement,
):
    """
    A revealed class disputes the inferred one only when both answer and the revealed
    one is not the inferred class or a subclass of it.
    """
    assert agreement.disputes_inference == (
        agreement
        in {ReceiverAgreement.BASE_CLASS_REVEALED, ReceiverAgreement.UNRELATED_CLASSES}
    )


# %% the pull requests triaged


def test_a_pull_request_reference_names_its_rules():
    """
    A reference names the repository, the number and the opt-in rules.
    """
    case = PullRequestCase.parse("owner/name#12:module-documentation")

    assert case == PullRequestCase(
        Repository("owner", "name"),
        12,
        frozenset({TriageRule.MODULE_DOCUMENTATION}),
    )


def test_a_reference_of_another_shape_is_refused():
    """
    A reference without a number names no pull request.
    """
    with pytest.raises(ValueError):
        PullRequestCase.parse("owner/name")

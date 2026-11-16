"""
Tests for the receiver inference experiment: reading what type checkers reveal, probing
files for it and answering the triage's questions with it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from basstler.experiments.receiver_inference.experiment import (
    InferringTriage,
    PullRequestCase,
)
from basstler.experiments.receiver_inference.probes import (
    REVEAL_FUNCTION,
    AnswerRecording,
    ExpressionSpan,
    FileProbe,
    NoInference,
    ReceiverQuestion,
    RevealedInference,
)
from basstler.experiments.receiver_inference.type_checkers import (
    Mypy,
    Pyrefly,
    Pyright,
    RevealedType,
    SourcePosition,
    TypeChecker,
)
from basstler.experiments.tool_installation import CommandRun, ToolInstallation
from basstler.github.repository import Repository
from basstler.review_triage.comparison import (
    FileTriager,
    FileVerdict,
    JudgmentContext,
    MechanicalFile,
)
from basstler.review_triage.keyword_arguments import KeywordChange
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.rules import TriageRule
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
            Pyrefly,
            "pyrefly-report.json",
            [RevealedType(SourcePosition(PROBED_PATH, 5, 20), "Plotter")],
        ),
    ],
)
def test_each_checker_reports_the_types_it_revealed_at_their_arguments(
    checker: type[TypeChecker],
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
    :return: The span of the receiver of every method call in it, but ``print``'s.
    """
    return [
        ExpressionSpan.of(node.func.value, text)
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]


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
    answering = AnswerRecording(RevealedInference(answers))

    verdict = triaged_with(sample, answering)

    assert verdict == MechanicalFile(
        sample.change(), frozenset({KeywordChange.KEYWORD_ARGUMENTS})
    )
    assert (unanswered.answered, answering.answered) == (set(), unanswered.asked)


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

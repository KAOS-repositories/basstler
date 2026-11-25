"""
Judging calls that pass positional arguments by keyword, and parameters made keyword-
only, against the base commit's definitions.
"""

from __future__ import annotations

import ast

import pytest

from basstler.review_triage.comparison import (
    Difference,
    FileNeedingReview,
    FileVerdict,
    FileTriager,
    JudgmentContext,
    MechanicalChange,
    MechanicalFile,
    ProseComparison,
    UnprovenDifference,
)
from basstler.review_triage.keyword_arguments import (
    KEYWORD_RULES,
    KeywordArgumentComparison,
    KeywordChange,
    UnprovenBinding,
    UnprovenDecorator,
    UnprovenKeywordCall,
)
from basstler.review_triage.python_source import ImportBindings, PythonSource
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.tree_matching import TreeMatcher

from .samples import FileSample

# %% verdicts


def triaged(sample: FileSample, renames: RenameMap) -> FileVerdict:
    """
    :param sample: A file in two versions.
    :param renames: The renames of the pull request.
    :return: The sample's verdict, its base version's definitions as the base commit's.
    """
    triager = FileTriager(
        JudgmentContext(renames, sample.base_definitions()),
        (KeywordArgumentComparison(), ProseComparison()),
    )
    return triager.triage(sample.change())


@pytest.mark.parametrize(
    ("sample", "kinds"),
    [
        (FileSample.KEYWORD_ARGUMENTS_ADDED, {KeywordChange.KEYWORD_ARGUMENTS}),
        (
            FileSample.KEYWORD_ARGUMENTS_ADDED_THROUGH_IMPORT_ALIAS,
            {KeywordChange.KEYWORD_ARGUMENTS},
        ),
        (
            FileSample.DOCSTRING_EXAMPLE_KEYWORD_ARGUMENTS,
            {KeywordChange.KEYWORD_ARGUMENTS},
        ),
        (FileSample.KEYWORD_ONLY_PARAMETERS, {KeywordChange.KEYWORD_ONLY}),
        (FileSample.IDENTITY_DECORATOR_ADDED, {KeywordChange.IDENTITY_DECORATORS}),
        (
            FileSample.IDENTITY_DECORATOR_IMPORTED,
            {KeywordChange.IDENTITY_DECORATORS, MechanicalChange.IMPORTS},
        ),
        (FileSample.CODE_REFORMATTED, {MechanicalChange.FORMATTING}),
    ],
)
def test_a_call_binding_as_before_is_mechanical(
    sample: FileSample, kinds: set[KeywordChange]
):
    """
    Keywords naming the parameters the base definitions bound the arguments to, in the
    code or in a docstring's python example, keyword-only parameters and added identity
    decorators, imported or not, are mechanical.
    """
    assert triaged(sample, RenameMap()) == MechanicalFile(
        sample.change(), frozenset(kinds)
    )


@pytest.mark.parametrize(
    "sample",
    [
        FileSample.KEYWORD_ARGUMENTS_SWAPPED,
        FileSample.KEYWORD_ARGUMENTS_REORDERED,
        FileSample.KEYWORD_ARGUMENTS_UNKNOWN_CALLEE,
        FileSample.BEHAVIOUR_CHANGED,
    ],
)
def test_a_call_that_may_bind_differently_needs_review(sample: FileSample):
    """
    Keywords naming other parameters, arguments evaluated in another order and calls of
    a callee the base commit does not define need review.
    """
    assert triaged(sample, RenameMap()) == FileNeedingReview(sample.change())


@pytest.mark.parametrize(
    ("sample", "code"),
    [
        (FileSample.BEHAVIOUR_CHANGED, "return width + height"),
        (FileSample.STATEMENT_APPENDED, "print(total)"),
        (FileSample.DOCSTRING_EXAMPLE_CHANGED, "assert area(2.0, 4.0) == 8.0"),
    ],
)
def test_code_changed_beyond_the_rules_is_the_reason_for_review(
    sample: FileSample, code: str
):
    """
    Code the rules cannot match names the head line where it stops matching: a changed
    expression, the first statement a body gains, or a docstring example's line.
    """
    assert triaged(sample, RenameMap()).reasons == (
        UnprovenDifference(sample.head_line(code), Difference.CODE_CHANGED),
    )


def test_the_plain_comparison_verdicts_are_kept(old_name_renamed: RenameMap):
    """
    A change the plain Python comparison finds mechanical keeps its kinds.
    """
    assert triaged(FileSample.IDENTIFIER_RENAMED, old_name_renamed).kinds == {
        MechanicalChange.IMPORTS,
        MechanicalChange.RENAME,
    }


# %% receivers of inferred classes


@pytest.mark.parametrize(
    "sample", [FileSample.RECEIVER_TYPE_INFERRED, FileSample.RECEIVER_TYPE_FOLLOWED]
)
def test_a_method_of_a_receiver_whose_class_is_inferred_is_resolved(
    sample: FileSample,
):
    """
    Calls on an instance a class makes, an attribute declares, a function returns, a
    type variable binds or a container holds, through loops, comprehensions, ``next``
    and names bound alike several times, reach only that class's methods.
    """
    assert triaged(sample, RenameMap()) == MechanicalFile(
        sample.change(), frozenset({KeywordChange.KEYWORD_ARGUMENTS})
    )


def test_an_imported_decorator_not_returning_what_it_decorates_needs_review():
    """
    An added decorator the head imports is the reason for review when its definition
    does not return what it decorates.
    """
    sample = FileSample.IMPORTED_DECORATOR_NOT_IDENTITY
    decorator_line = sample.head_line("@called_positionally")
    assert triaged(sample, RenameMap()) == FileNeedingReview(
        sample.change(), (UnprovenDecorator(decorator_line, "called_positionally"),)
    )


@pytest.mark.parametrize(
    ("sample", "unproven"),
    [
        (
            FileSample.RECEIVER_TYPE_UNKNOWN,
            UnprovenKeywordCall(
                16,
                "plot",
                UnprovenBinding.RECEIVER_CLASS_UNKNOWN,
                ("GoalPlotter.plot",),
            ),
        ),
        (
            FileSample.RECEIVER_BINDS_DIFFERENTLY,
            UnprovenKeywordCall(
                14, "plot", UnprovenBinding.BINDS_DIFFERENTLY, ("GoalPlotter.plot",)
            ),
        ),
        (
            FileSample.RECEIVER_OVERRIDES_INCOMPATIBLE,
            UnprovenKeywordCall(
                20,
                "plot",
                UnprovenBinding.INCOMPATIBLE_OVERRIDES,
                ("GoalPlotter.plot",),
            ),
        ),
    ],
)
def test_a_call_not_shown_to_bind_as_before_is_the_reason_for_review(
    sample: FileSample, unproven: UnprovenKeywordCall
):
    """
    A file needing review names each call not shown to bind as before, why, and the
    definitions it may reach that bind the arguments otherwise.
    """
    assert triaged(sample, RenameMap()).reasons == (unproven,)


def test_the_reason_for_review_names_the_line_below_the_module_documentation():
    """
    The line a reason names counts the lines of the module's documentation, which the
    comparison leaves out.
    """
    sample = FileSample.DOCUMENTED_RECEIVER_BINDS_DIFFERENTLY
    assert triaged(sample, RenameMap()).reasons == (
        UnprovenKeywordCall(
            sample.head_line("plotter.plot(file_name=3)"),
            "plot",
            UnprovenBinding.BINDS_DIFFERENTLY,
            ("GoalPlotter.plot",),
        ),
    )


def test_the_explanation_names_the_definitions_binding_otherwise():
    """
    The explanation of a call not shown to bind as before lists the definitions that
    bind its arguments otherwise.
    """
    cause = UnprovenBinding.BINDS_DIFFERENTLY
    reason = UnprovenKeywordCall(
        1, "plot", cause, ("FirstPlotter.plot", "Plotter.plot")
    )
    assert reason.explanation == (
        f"`plot` - {cause}: `FirstPlotter.plot`, `Plotter.plot`"
    )


def test_a_name_bound_to_different_classes_leaves_the_receiver_unknown():
    """
    A name assigned instances of two classes, or bound by a lambda's parameter, a
    comprehension's loop or a ``match`` capture over an outer binding, gives the
    receiver no class.
    """
    reasons = triaged(FileSample.RECEIVER_TYPE_AMBIGUOUS, RenameMap()).reasons
    assert reasons == tuple(
        UnprovenKeywordCall(
            line,
            "plot",
            UnprovenBinding.RECEIVER_CLASS_UNKNOWN,
            ("TrajectoryPlotter.plot",),
        )
        for line in (21, 25, 30, 38)
    )


# %% receivers rebound in order


def test_a_receiver_reassigned_has_the_class_of_its_last_assignment():
    """
    A name reassigned has, at a call, the class of the assignment that last ran before
    it, through branches that do not rebind it and calls of the name itself.
    """
    sample = FileSample.RECEIVER_TYPE_REASSIGNED
    assert triaged(sample, RenameMap()) == MechanicalFile(
        sample.change(), frozenset({KeywordChange.KEYWORD_ARGUMENTS})
    )


def test_a_parameter_reassigned_from_its_own_call_has_its_annotated_class():
    """
    A parameter the call's own assignment rebinds has, at the call, the class it is
    annotated with.
    """
    sample = FileSample.RECEIVER_PARAMETER_REASSIGNED
    assert triaged(sample, RenameMap()) == MechanicalFile(
        sample.change(), frozenset({KeywordChange.KEYWORD_ARGUMENTS})
    )


def test_a_parameter_a_loop_rebinds_has_no_class():
    """
    A parameter a loop around the call rebinds gives the receiver no class.
    """
    sample = FileSample.RECEIVER_PARAMETER_REBOUND_IN_LOOP
    assert triaged(sample, RenameMap()).reasons == (
        UnprovenKeywordCall(
            sample.head_line("current.dot(other=table)"),
            "dot",
            UnprovenBinding.RECEIVER_CLASS_UNKNOWN,
            ("ProbabilityTable.dot",),
        ),
    )


def test_a_receiver_that_may_be_rebound_before_the_call_has_no_class():
    """
    A name a loop, a closure, a ``try`` body or a condition may rebind before the call
    gives the receiver no class.
    """
    reasons = triaged(FileSample.RECEIVER_REBOUND_OUT_OF_ORDER, RenameMap()).reasons
    assert reasons == tuple(
        UnprovenKeywordCall(
            line,
            "plot",
            UnprovenBinding.RECEIVER_CLASS_UNKNOWN,
            ("GoalPlotter.plot",),
        )
        for line in (17, 28, 38, 44)
    )


# %% the comparison of trees


def test_a_failed_attempt_keeps_no_findings():
    """
    Trying a match that fails drops the findings its inner calls recorded.
    """
    base = ast.parse("total(scale(1.0), 2.0)").body[0]
    head = ast.parse("total(scale(value=1.0), 3.0)").body[0]
    matcher = TreeMatcher(KEYWORD_RULES, ImportBindings(frozenset()))
    assert (matcher.attempt(base, head), matcher.findings) == (False, [])


@pytest.mark.parametrize(
    ("function", "types"),
    [
        (
            "def f(shape: Shape, size: int | None, other): pass",
            {"shape": "Shape", "size": "int"},
        ),
        ("def f(shape: Shape):\n    shape = make()", {}),
        ("def f(items: list[Shape], maybe: Optional[Shape]): pass", {"maybe": "Shape"}),
    ],
)
def test_only_parameters_kept_as_annotated_have_a_class(function: str, types: dict):
    """
    A parameter has a class when its annotation allows one, ``None`` aside, and the
    function never assigns to it.
    """
    assert PythonSource.annotated_parameters(ast.parse(function).body[0]) == types

"""
Answering the receivers basstler's own inference leaves open with the classes a type
checker reveals in the base commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

from basstler.command_run import CommandRun
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.comparison import FileNeedingReview, MechanicalFile
from basstler.review_triage.commit_tree import CommitModules
from basstler.review_triage.keyword_arguments import KeywordChange
from basstler.review_triage.triage import PullRequestTriager
from basstler.review_triage.type_checkers import RevealedType, TypeChecker

from ..scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import ReceiverCheckSample

DRAWING_SCRIPT = PurePosixPath("scripts/draw.py")
"""
The file of the samples that passes an argument by keyword.
"""

# %% a checker that must not run


@dataclass(frozen=True)
class CheckerFailingTheTest(TypeChecker):
    """
    A type checker failing the test that runs it.
    """

    @property
    def program(self) -> tuple[str, ...]:
        return ("unused",)

    def command(
        self, files: list[str], search_paths: list[Path], workspace: Path
    ) -> list[str]:
        pytest.fail("the type checker ran")

    def revealed_types(self, run: CommandRun, checkout: Path) -> list[RevealedType]:
        return []


# %% the samples


@pytest.fixture
def unannotated_factory(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample calling the factory whose return is unannotated, committed.
    """
    return committed_pull_request(
        scratch_repository, ReceiverCheckSample.BASE_TREE, ReceiverCheckSample.HEAD_TREE
    )


@pytest.fixture
def annotated_factory(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample calling the factory whose return is annotated, committed.
    """
    return committed_pull_request(
        scratch_repository,
        ReceiverCheckSample.ANSWERED_BASE_TREE,
        ReceiverCheckSample.ANSWERED_HEAD_TREE,
    )


def verdict_on_script(
    triager: PullRequestTriager, changes: PullRequestChanges
) -> MechanicalFile | FileNeedingReview:
    """
    :param triager: The triager.
    :param changes: A sample pull request.
    :return: The verdict on the script passing an argument by keyword.
    """
    [verdict] = [
        file
        for file in triager.triage(changes).files
        if file.change.path == DRAWING_SCRIPT
    ]
    return verdict


# %% the fallback


def test_a_receiver_only_the_type_checker_reveals_is_resolved(
    unannotated_factory: PullRequestChanges,
):
    """
    A call on what an unannotated factory returns reaches the method of the class the
    type checker reveals, imported from a package under a source directory.
    """
    verdict = verdict_on_script(PullRequestTriager(), unannotated_factory)

    assert verdict == MechanicalFile(
        verdict.change, frozenset({KeywordChange.KEYWORD_ARGUMENTS})
    )


def test_without_a_type_checker_the_receiver_stays_unknown(
    unannotated_factory: PullRequestChanges,
):
    """
    With the type checker turned off, the call is left for review.
    """
    verdict = verdict_on_script(
        PullRequestTriager(type_checker=None), unannotated_factory
    )

    assert isinstance(verdict, FileNeedingReview)


def test_the_type_checker_runs_only_for_a_receiver_left_unanswered(
    annotated_factory: PullRequestChanges,
):
    """
    A pull request whose receivers basstler's inference answers never runs the checker.
    """
    verdict = verdict_on_script(
        PullRequestTriager(type_checker=CheckerFailingTheTest()), annotated_factory
    )

    assert verdict.kinds == {KeywordChange.KEYWORD_ARGUMENTS}


# %% where imports resolve


def test_imports_resolve_in_the_directories_holding_top_level_packages(
    unannotated_factory: PullRequestChanges,
):
    """
    The import roots are the commit's root and every directory holding a package that
    no package encloses, not the directory holding a package nested deeper in one.
    """
    modules = CommitModules(unannotated_factory.commits.base_tree)

    assert modules.import_roots == (PurePosixPath("."), PurePosixPath("src"))

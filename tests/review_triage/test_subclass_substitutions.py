"""
Triaging the files that replace a class by a subclass made only of members moved down
from it.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath

import pytest

from basstler.review_triage.comparison import MechanicalChange
from basstler.github.pull_request_changes import PullRequestChanges
from basstler.review_triage.renames import Rename
from basstler.review_triage.subclass_substitutions import SubclassSubstitutionDetection
from basstler.review_triage.triage import PullRequestTriager

from ..scratch_repository import ScratchRepository
from .conftest import committed_pull_request
from .samples import SubclassSubstitutionSample

# %% the sample

CALLER = PurePosixPath("caller.py")
"""
The file of the sample switching to the subclass.
"""

SUBCLASS_MODULE = PurePosixPath("package/named_branch.py")
"""
The module of the sample adding the subclass.
"""


@pytest.fixture
def subclass_substitution(scratch_repository: ScratchRepository) -> PullRequestChanges:
    """
    :return: The sample moving a property down into a new subclass, committed.
    """
    return committed_pull_request(
        scratch_repository,
        SubclassSubstitutionSample.BASE_TREE,
        SubclassSubstitutionSample.HEAD_TREE,
    )


def with_subclass_module(
    changes: PullRequestChanges, head_text: str
) -> PullRequestChanges:
    """
    :param changes: The subclass-substitution sample.
    :param head_text: Another head version of :data:`SUBCLASS_MODULE`.
    :return: The sample with that version in place of the committed one.
    """
    return replace(
        changes,
        files=tuple(
            replace(change, head_text=head_text)
            if change.path == SUBCLASS_MODULE
            else change
            for change in changes.files
        ),
    )


# %% detection


def test_a_subclass_of_members_moved_down_substitutes_its_class(
    subclass_substitution: PullRequestChanges,
):
    """
    The class is substituted by the subclass, both as a name and as a dotted path.
    """
    detection = SubclassSubstitutionDetection()
    assert detection.decisions(subclass_substitution).accepted == (
        Rename("Branch", "NamedBranch", detection),
        Rename("package.branch.Branch", "package.named_branch.NamedBranch", detection),
    )


# %% triage


def test_files_switching_to_the_subclass_or_keeping_the_class_are_mechanical(
    subclass_substitution: PullRequestChanges,
):
    """
    The caller switching to the subclass and the file keeping the class are mechanical;
    the class losing a member and the module adding the subclass are not.
    """
    triage = PullRequestTriager().triage(subclass_substitution)
    assert {file.change.path: file.kinds for file in triage.mechanical_files} == {
        CALLER: frozenset(
            {MechanicalChange.IMPORTS, MechanicalChange.SUBCLASS_SUBSTITUTED}
        ),
        PurePosixPath("keeper.py"): frozenset({MechanicalChange.FORMATTING}),
    }


@pytest.mark.parametrize(
    "head_text",
    [
        pytest.param(
            SubclassSubstitutionSample.HEAD_TREE.path.joinpath(SUBCLASS_MODULE)
            .read_text()
            .replace(
                'f"{self.name} on {self.remote}"', 'f"{self.name} at {self.remote}"'
            ),
            id="member-changed",
        ),
        pytest.param(
            SubclassSubstitutionSample.HEAD_TREE.path.joinpath(
                SUBCLASS_MODULE
            ).read_text()
            + '\n    depth: int = 1\n    """\n    How many commits to fetch.\n    """\n',
            id="field-added",
        ),
        pytest.param(
            SubclassSubstitutionSample.HEAD_TREE.path.joinpath(SUBCLASS_MODULE)
            .read_text()
            .replace("@dataclass(frozen=True)", "@dataclass"),
            id="decorator-changed",
        ),
        pytest.param(
            SubclassSubstitutionSample.HEAD_TREE.path.joinpath(
                SUBCLASS_MODULE
            ).read_text()
            + "\n    def reference(self) -> str:\n        return self.name\n",
            id="member-overridden",
        ),
    ],
)
def test_a_caller_of_a_subclass_doing_more_needs_review(
    subclass_substitution: PullRequestChanges, head_text: str
):
    """
    A subclass that changes a moved member, adds a field, is decorated otherwise or
    overrides a member of its class is no substitute, so its caller needs review.
    """
    triage = PullRequestTriager().triage(
        with_subclass_module(subclass_substitution, head_text)
    )
    assert CALLER in {file.change.path for file in triage.files_needing_review}

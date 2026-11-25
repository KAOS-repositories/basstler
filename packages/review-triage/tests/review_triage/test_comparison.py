"""
Judging one file's change as mechanical or needing review.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import PurePosixPath

import pytest

from basstler.git.commit_range import FileVersions
from basstler.review_triage.comparison import (
    ChangeKind,
    ChangeKinds,
    Difference,
    FileJudgment,
    FileNeedingReview,
    FileTriager,
    ImportDifference,
    ImportMismatch,
    JudgmentContext,
    MechanicalChange,
    MechanicalFile,
    ProseComparison,
    PythonComparison,
    ReviewReason,
    UnprovenDifference,
)
from basstler.review_triage.renames import Rename, RenameMap
from basstler.review_triage.rules import DEFAULT_RULES, TriageRule

from .samples import TEMPLATE_REINDENTED, FileSample
from basstler.text_file import TextFile

# %% file contents


@pytest.mark.parametrize(
    ("sample", "kinds"),
    [
        (FileSample.IMPORTS_REORDERED, {MechanicalChange.IMPORTS}),
        (FileSample.IMPORT_ADDED_UNDER_STAR_IMPORT, {MechanicalChange.IMPORTS}),
        (
            FileSample.IDENTIFIER_RENAMED,
            {MechanicalChange.IMPORTS, MechanicalChange.RENAME},
        ),
        (FileSample.DOCSTRING_REFLOWED, {MechanicalChange.FORMATTING}),
        (FileSample.CODE_REFORMATTED, {MechanicalChange.FORMATTING}),
        (FileSample.DOCUMENTATION_RENAMED, {MechanicalChange.RENAME}),
        (
            FileSample.DOCUMENTATION_REFLOWED,
            {MechanicalChange.RENAME, MechanicalChange.FORMATTING},
        ),
    ],
)
def test_a_mechanical_change_is_reported_with_its_kinds(
    sample: FileSample, kinds: set[MechanicalChange], old_name_renamed: RenameMap
):
    """
    Each sample whose change cannot alter what the file does or says is mechanical, with
    the kinds of change it consists of.
    """
    change = sample.change()
    assert FileTriager(JudgmentContext(old_name_renamed)).triage(
        change
    ) == MechanicalFile(change, frozenset(kinds))


def test_a_future_import_added_is_mechanical():
    """
    A ``__future__`` import the head version has and the base version lacks is a change
    of imports.
    """
    with_import = FileSample.IMPORT_ADDED_UNUSED.change().base_text
    without_import = with_import.split("\n", 2)[2]
    change = replace(
        FileSample.IMPORT_ADDED_UNUSED.change(),
        base_text=without_import,
        head_text=with_import,
    )

    assert FileTriager(JudgmentContext()).triage(change) == MechanicalFile(
        change, frozenset({MechanicalChange.IMPORTS})
    )


@pytest.mark.parametrize(
    "sample",
    [
        FileSample.IMPORT_SOURCE_CHANGED,
        FileSample.IMPORT_ADDED_UNUSED,
        FileSample.IMPORT_REMOVED_UNUSED,
        FileSample.IMPORT_ADDED_FROM_OTHER_MODULE,
        FileSample.STRING_LITERAL_RENAMED,
        FileSample.DOCSTRING_REWORDED,
        FileSample.BEHAVIOUR_CHANGED,
    ],
)
def test_a_change_of_meaning_needs_review(
    sample: FileSample, old_name_renamed: RenameMap
):
    """
    A changed import source, an import the code does not use, an import of a name
    another module's star import supplied, or a changed string literal, docstring
    wording or expression needs review, renames or not.
    """
    change = sample.change()
    assert FileTriager(JudgmentContext(old_name_renamed)).triage(
        change
    ) == FileNeedingReview(change)


@pytest.mark.parametrize(
    ("sample", "code", "expected"),
    [
        (
            FileSample.IMPORT_SOURCE_CHANGED,
            "from pickle import loads",
            lambda line: ImportDifference(line, "loads", ImportMismatch.SOURCE_CHANGED),
        ),
        (
            FileSample.IMPORT_ADDED_UNUSED,
            "import json",
            lambda line: ImportDifference(line, "json", ImportMismatch.ONLY_HEAD),
        ),
        (
            FileSample.IMPORT_REMOVED_UNUSED,
            "from __future__ import annotations",
            lambda line: ImportDifference(line, "json", ImportMismatch.ONLY_BASE),
        ),
        (
            FileSample.IMPORT_ADDED_FROM_OTHER_MODULE,
            "from posixpath import join",
            lambda line: ImportDifference(line, "join", ImportMismatch.ONLY_HEAD),
        ),
        (
            FileSample.STRING_LITERAL_RENAMED,
            'COMMAND = "new_name"',
            lambda line: UnprovenDifference(line, Difference.TEXT_CHANGED),
        ),
        (
            FileSample.DOCSTRING_REWORDED,
            '"""',
            lambda line: UnprovenDifference(line, Difference.DOCSTRING_REWORDED),
        ),
        (
            FileSample.COMMENT_REWORDED,
            "# Both sides are in feet.",
            lambda line: UnprovenDifference(line, Difference.COMMENT_REWORDED),
        ),
        (
            FileSample.BEHAVIOUR_CHANGED,
            "return width + height",
            lambda line: UnprovenDifference(line, Difference.TEXT_CHANGED),
        ),
    ],
)
def test_a_change_of_meaning_names_the_part_not_proven(
    sample: FileSample, code: str, expected: Callable[[int], ReviewReason]
):
    """
    A file needing review names the import, docstring, comment or line the judgments
    could not prove mechanical, on the line of the head version showing *code*.
    """
    verdict = FileTriager(JudgmentContext()).triage(sample.change())
    assert verdict.reasons == (expected(sample.head_line(code)),)


def test_a_rename_the_pull_request_does_not_make_needs_review():
    """
    Renamed identifiers are mechanical only when the pull request makes the rename
    throughout.
    """
    change = FileSample.IDENTIFIER_RENAMED.change()
    assert FileTriager(JudgmentContext()).triage(change) == FileNeedingReview(change)


# %% whole files


def test_an_unchanged_moved_file_is_mechanical():
    """
    A file moved without changing its content is a move.
    """
    change = replace(
        FileSample.BEHAVIOUR_CHANGED.change(),
        head_text=FileSample.BEHAVIOUR_CHANGED.change().base_text,
        previous_path=PurePosixPath("old/sample.py"),
    )
    assert FileTriager(JudgmentContext()).triage(change) == MechanicalFile(
        change, frozenset({MechanicalChange.MOVE})
    )


@pytest.mark.parametrize(
    "change",
    [
        replace(FileSample.BEHAVIOUR_CHANGED.change(), base_text=None),
        replace(FileSample.BEHAVIOUR_CHANGED.change(), head_text=None),
        FileVersions(PurePosixPath("logo.png"), is_binary=True),
        replace(
            FileSample.DOCUMENTATION_RENAMED.change(), path=PurePosixPath("sample.yaml")
        ),
    ],
    ids=["added", "deleted", "binary", "unjudged type"],
)
def test_a_file_no_judgment_proves_mechanical_needs_review(change: FileVersions):
    """
    An added, deleted or binary file, or a changed file of a type nothing judges, needs
    review.
    """
    assert FileTriager(JudgmentContext()).triage(change) == FileNeedingReview(change)


@pytest.mark.parametrize(
    ("change", "difference"),
    [
        (
            replace(FileSample.BEHAVIOUR_CHANGED.change(), base_text=None),
            Difference.ADDED_FILE,
        ),
        (
            replace(FileSample.BEHAVIOUR_CHANGED.change(), head_text=None),
            Difference.DELETED_FILE,
        ),
        (
            FileVersions(PurePosixPath("logo.png"), is_binary=True),
            Difference.BINARY_FILE,
        ),
    ],
    ids=["added", "deleted", "binary"],
)
def test_a_whole_file_no_judgment_reads_is_the_reason_for_review(
    change: FileVersions, difference: Difference
):
    """
    An added, deleted or binary file needs review for being one, on its first line.
    """
    verdict = FileTriager(JudgmentContext()).triage(change)
    assert verdict.reasons == (UnprovenDifference(1, difference),)


# %% relative imports


def test_a_relative_import_following_its_file_s_move_is_mechanical():
    """
    A moved file whose relative import is respelled to reach the same module changes
    only its imports.
    """
    change = replace(
        FileSample.RELATIVE_IMPORT_MOVED.change(),
        path=PurePosixPath("tests/git/test_branch.py"),
        previous_path=PurePosixPath("tests/maintenance/test_branch.py"),
    )
    assert FileTriager(JudgmentContext()).triage(change) == MechanicalFile(
        change, frozenset({MechanicalChange.IMPORTS, MechanicalChange.MOVE})
    )


def test_a_relative_import_reaching_another_module_needs_review():
    """
    The same respelling in a file that did not move reaches another module.
    """
    change = replace(
        FileSample.RELATIVE_IMPORT_MOVED.change(),
        path=PurePosixPath("tests/git/test_branch.py"),
    )
    assert FileTriager(JudgmentContext()).triage(change) == FileNeedingReview(change)


# %% added package initializers


@pytest.mark.parametrize("text", ["", "\n"])
def test_an_added_empty_package_initializer_is_mechanical(text: str):
    change = FileVersions(PurePosixPath("package/__init__.py"), head_text=text)
    assert FileTriager(JudgmentContext()).triage(change) == MechanicalFile(
        change, frozenset({MechanicalChange.EMPTY_PACKAGE})
    )


@pytest.mark.parametrize(
    "change",
    [
        FileVersions(PurePosixPath("package/__init__.py"), head_text="VALUE = 1\n"),
        FileVersions(PurePosixPath("package/empty.py"), head_text=""),
    ],
    ids=["with code", "another module"],
)
def test_another_added_file_needs_review(change: FileVersions):
    assert FileTriager(JudgmentContext()).triage(change) == FileNeedingReview(change)


# %% other text files

MODULE_MOVED = RenameMap(
    (Rename("package.repository", "package.storage.repository", "test"),)
)
"""
The rename the template sample follows.
"""


def test_a_text_file_of_another_type_that_only_follows_a_rename_is_mechanical():
    """
    A template whose only change is a module rename is mechanical.
    """
    change = FileSample.TEMPLATE_RENAMED.change()
    assert FileTriager(JudgmentContext(MODULE_MOVED)).triage(change) == MechanicalFile(
        change, frozenset({MechanicalChange.RENAME})
    )


DEFINITION_MOVED = RenameMap(
    (
        Rename(
            "package.repository.Repository",
            "package.storage.repository.Repository",
            "test",
        ),
    )
)
"""
The rename of a definition to the same name in another module.
"""


def test_a_documented_import_of_a_moved_definition_is_mechanical():
    """
    An import line in documentation that only follows the module a definition moved to
    is mechanical, like the import of a Python file.
    """
    change = FileSample.DOCUMENTATION_IMPORT_MOVED.change()
    assert FileTriager(JudgmentContext(DEFINITION_MOVED)).triage(
        change
    ) == MechanicalFile(change, frozenset({MechanicalChange.RENAME}))


def test_a_text_file_of_another_type_whose_whitespace_changes_needs_review():
    """
    Whitespace can carry meaning in a file of unknown type, so a renamed line that is
    also reindented needs review.
    """
    change = replace(
        FileSample.TEMPLATE_RENAMED.change(),
        head_text=TextFile(TEMPLATE_REINDENTED).read(),
    )
    assert FileTriager(JudgmentContext(MODULE_MOVED)).triage(
        change
    ) == FileNeedingReview(change)


# %% rules


def test_a_reworded_module_documentation_is_mechanical_by_default():
    """
    A file whose only change is its module's documentation is mechanical unless the
    module documentation rule is turned off.
    """
    change = FileSample.MODULE_DOCUMENTATION_REWORDED.change()
    assert FileTriager(JudgmentContext()).triage(change) == MechanicalFile(
        change, frozenset({MechanicalChange.MODULE_DOCUMENTATION})
    )


def test_a_reworded_module_documentation_needs_review_once_its_rule_is_off():
    """
    With no rule on, reworded module documentation needs review.
    """
    change = FileSample.MODULE_DOCUMENTATION_REWORDED.change()
    assert FileTriager(JudgmentContext(rules=frozenset())).triage(
        change
    ) == FileNeedingReview(change)


@pytest.mark.parametrize(
    "sample",
    [FileSample.MODULE_DOCUMENTATION_AND_CODE_CHANGED, FileSample.DOCSTRING_REWORDED],
    ids=["code changes too", "documentation of a function"],
)
def test_the_module_documentation_rule_skips_nothing_else(sample: FileSample):
    """
    Changed code, and the documentation of anything but the module, need review under
    the module documentation rule too.
    """
    change = sample.change()
    assert FileTriager(JudgmentContext()).triage(change) == FileNeedingReview(change)


@pytest.mark.parametrize(
    ("path", "is_test"),
    [
        ("tests/shapes.py", True),
        ("robot/test/shapes.py", True),
        ("robot/test_shapes.py", True),
        ("robot/shapes_test.py", True),
        ("robot/conftest.py", True),
        ("robot/shapes.py", False),
        ("robot/testing/shapes.py", False),
        ("robot/contest_shapes.py", False),
    ],
)
def test_docstrings_added_or_removed_are_mechanical_by_default_only_in_tests(
    path: str, is_test: bool
):
    """
    Docstrings that a function, class or field gains or loses are mechanical by default
    in a test file alone.
    """
    change = replace(
        FileSample.DOCSTRINGS_ADDED_AND_REMOVED.change(), path=PurePosixPath(path)
    )
    expected = (
        MechanicalFile(
            change, frozenset({MechanicalChange.DOCSTRINGS_ADDED_OR_REMOVED})
        )
        if is_test
        else FileNeedingReview(change)
    )
    assert FileTriager(JudgmentContext()).triage(change) == expected


def test_docstrings_added_or_removed_are_mechanical_once_their_rule_is_on():
    """
    Under the rule for every file, docstrings gained or lost outside the tests are
    mechanical too.
    """
    change = FileSample.DOCSTRINGS_ADDED_AND_REMOVED.change()
    rules = DEFAULT_RULES | {TriageRule.DOCSTRINGS_ADDED_OR_REMOVED}
    assert FileTriager(JudgmentContext(rules=rules)).triage(change) == MechanicalFile(
        change, frozenset({MechanicalChange.DOCSTRINGS_ADDED_OR_REMOVED})
    )


def test_docstrings_added_or_removed_in_a_test_need_review_once_its_rule_is_off():
    """
    With the rule for test files turned off, a test's docstrings gained or lost need
    review.
    """
    change = replace(
        FileSample.DOCSTRINGS_ADDED_AND_REMOVED.change(),
        path=PurePosixPath("tests/test_shapes.py"),
    )
    rules = DEFAULT_RULES - {TriageRule.TEST_DOCSTRINGS_ADDED_OR_REMOVED}
    assert FileTriager(JudgmentContext(rules=rules)).triage(
        change
    ) == FileNeedingReview(change)


@pytest.mark.parametrize(
    "sample",
    [FileSample.DOCSTRING_ADDED_AND_CODE_CHANGED, FileSample.DOCSTRING_REWORDED],
    ids=["code changes too", "a docstring reworded"],
)
def test_the_docstrings_added_or_removed_rule_skips_nothing_else(sample: FileSample):
    """
    Changed code, and a docstring both versions have but word differently, need review
    under the rule too.
    """
    change = sample.change()
    rules = DEFAULT_RULES | {TriageRule.DOCSTRINGS_ADDED_OR_REMOVED}
    assert FileTriager(JudgmentContext(rules=rules)).triage(
        change
    ) == FileNeedingReview(change)


# %% extending the triage


class GeneratedChange(ChangeKind):
    """
    The kind of change an extension declares.
    """

    GENERATED = "generated"


class GeneratedFileJudgment(FileJudgment):
    """
    Judges every file under a generated directory mechanical.
    """

    def applies_to(self, change: FileVersions) -> bool:
        return change.path.parts[0] == "generated"

    def changes(
        self, change: FileVersions, context: JudgmentContext
    ) -> ChangeKinds | None:
        return frozenset({GeneratedChange.GENERATED})


def test_an_extension_judgment_decides_the_files_it_applies_to():
    """
    A judgment placed first decides its files, with change kinds its extension declares.
    """
    change = replace(
        FileSample.BEHAVIOUR_CHANGED.change(), path=PurePosixPath("generated/sample.py")
    )
    triager = FileTriager(
        JudgmentContext(),
        (GeneratedFileJudgment(), PythonComparison(), ProseComparison()),
    )
    assert triager.triage(change) == MechanicalFile(
        change, frozenset({GeneratedChange.GENERATED})
    )

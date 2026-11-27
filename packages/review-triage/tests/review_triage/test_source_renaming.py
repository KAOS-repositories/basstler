"""
Renaming a Python file's text where the triage applies renames.
"""

from __future__ import annotations

from basstler.review_triage.python_source import PythonSource
from basstler.review_triage.renames import RenameMap
from basstler.review_triage.source_renaming import SourceRenaming

from .samples import FileSample

# %% what is renamed


def test_identifiers_imports_documentation_and_comments_are_renamed(
    old_name_renamed: RenameMap,
):
    change = FileSample.IDENTIFIER_RENAMED.change()
    renamed = SourceRenaming(PythonSource(change.base_text), old_name_renamed)
    assert renamed.renamed_text() == change.head_text


def test_a_string_literal_is_not_renamed(old_name_renamed: RenameMap):
    change = FileSample.STRING_LITERAL_RENAMED.change()
    renamed = SourceRenaming(PythonSource(change.base_text), old_name_renamed)
    assert renamed.renamed_text() == change.base_text

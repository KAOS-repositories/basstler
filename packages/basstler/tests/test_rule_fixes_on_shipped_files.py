"""
Tests for what the code-rule fixes leave alone in files other distributions ship.
"""

from __future__ import annotations

from basstler.code_modification.source_file import EditablePythonSourceFile
from basstler.code_rules.fixes import SourceFixer
from basstler.code_rules.text_file_usage import TextFileChecker
from basstler.locations import PackageLocation

# %% files a checker skips


def test_a_checker_that_skips_a_file_fixes_nothing_in_it():
    """
    The program that runs without ``basstler`` keeps the path methods it reads with.
    """
    source_file = EditablePythonSourceFile(PackageLocation.UPSTREAM_REVIEWS_FETCH)

    fixed = SourceFixer((TextFileChecker(),)).fix_module(source_file)

    assert fixed.result.code == source_file.read()

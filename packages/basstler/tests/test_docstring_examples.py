"""
Tests that the examples in the docstrings of the helpers the suites share give the
output they show.
"""

from __future__ import annotations

import pytest

from basstler_testing.docstring_examples import DocstringExample, SourceTree


@pytest.mark.parametrize("example", SourceTree.of_test_support().examples(), ids=str)
def test_a_docstring_example_gives_the_output_it_shows(example: DocstringExample):
    """
    Each example is run in the namespace of the module it documents.
    """
    example.assert_holds()

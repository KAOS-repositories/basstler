"""
Splitting a docstring into its python code examples and the prose around them.
"""

from __future__ import annotations

from basstler.review_triage.docstring_examples import (
    EXAMPLE_PLACEHOLDER,
    CodeExample,
    DocumentedExamples,
)
from basstler.text_file import TextFile

from basstler_testing.constants.paths import DatasetLocation

DOCUMENTED = DatasetLocation.REVIEW_TRIAGE / "docstring-examples" / "documented.txt"
"""
A docstring with two python code blocks, the first with a directive option.
"""

# %% splitting


def test_each_python_code_block_is_an_example_starting_on_its_first_code_line():
    """
    Each ``code-block`` or ``code`` directive's block, options and the blank line after
    them aside, is an example, dedented, at the line its code starts on.
    """
    lines = TextFile(DOCUMENTED).read().split("\n")
    first = lines.index("    loader = FileLoader()")
    second = lines.index("    print(1)")
    assert DocumentedExamples.from_docstring("\n".join(lines)).examples == (
        CodeExample(
            'loader = FileLoader()\nif loader:\n    loader.load(name="a")\n', first
        ),
        CodeExample("print(1)\n", second),
    )


def test_the_prose_keeps_everything_but_the_code():
    """
    The prose keeps the directives, their options and the text around the examples, a
    placeholder standing for each example's code.
    """
    split = DocumentedExamples.from_docstring(TextFile(DOCUMENTED).read())
    assert split.prose.split("\n") == [
        "Load a file.",
        "",
        ".. code-block:: python",
        "    :linenos:",
        "",
        EXAMPLE_PLACEHOLDER,
        "",
        "Prose after the example.",
        "",
        ".. code:: python3",
        "",
        EXAMPLE_PLACEHOLDER,
        "",
    ]

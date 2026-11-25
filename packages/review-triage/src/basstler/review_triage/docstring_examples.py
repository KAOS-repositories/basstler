"""
The python code examples of a docstring, where they stand in it.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass

PYTHON_CODE_DIRECTIVE = re.compile(
    r"^(?P<indent>[ \t]*)\.\. (?:code-block|code|sourcecode)::[ \t]+python3?[ \t]*$"
)
"""
A reStructuredText directive opening a python code block, on a line of its own.
"""

DIRECTIVE_OPTION = re.compile(r"^[ \t]+:[\w-]+:")
"""
An option line of a directive, such as ``:linenos:``.
"""

EXAMPLE_PLACEHOLDER = "\0code example\0"
"""
What stands for a code example in the prose around it.
"""

# %% one example


@dataclass(frozen=True)
class CodeExample:
    """
    The code of one python code block of a docstring.
    """

    code: str
    """
    The block's code, dedented.
    """

    first_line: int
    """
    The line of the docstring the code starts on, counted from zero.
    """


# %% a docstring split into prose and examples


@dataclass(frozen=True)
class DocumentedExamples:
    """
    A docstring in its python code examples and the prose around them.
    """

    prose: str
    """
    The docstring with each example's code replaced by :data:`EXAMPLE_PLACEHOLDER`.
    """

    examples: tuple[CodeExample, ...]
    """
    Each python code block's code, in docstring order.
    """

    @classmethod
    def from_docstring(cls, docstring: str) -> DocumentedExamples:
        """
        :param docstring: The text of a documentation string.
        :return: It split into its python code blocks and the prose around them.
        """
        lines = docstring.split("\n")
        prose: list[str] = []
        examples: list[CodeExample] = []
        number = 0
        while number < len(lines):
            line = lines[number]
            prose.append(line)
            number += 1
            directive = PYTHON_CODE_DIRECTIVE.match(line)
            if directive is None:
                continue
            while number < len(lines) and DIRECTIVE_OPTION.match(lines[number]):
                prose.append(lines[number])
                number += 1
            end = cls.block_end(lines, number, len(directive["indent"]))
            while end > number and not lines[end - 1].strip():
                end -= 1
            first = next(
                (index for index in range(number, end) if lines[index].strip()), end
            )
            if first == end:
                continue
            prose.extend(lines[number:first])
            prose.append(EXAMPLE_PLACEHOLDER)
            examples.append(
                CodeExample(textwrap.dedent("\n".join(lines[first:end])) + "\n", first)
            )
            number = end
        return cls("\n".join(prose), tuple(examples))

    @staticmethod
    def block_end(lines: list[str], start: int, directive_indent: int) -> int:
        """
        :param lines: The docstring's lines.
        :param start: The line after a directive and its options.
        :param directive_indent: How far the directive is indented.
        :return: The first line from *start* on that is not blank and indented no
            further than the directive, else the number of lines.
        """
        return next(
            (
                index
                for index in range(start, len(lines))
                if lines[index].strip()
                and len(lines[index]) - len(lines[index].lstrip()) <= directive_indent
            ),
            len(lines),
        )

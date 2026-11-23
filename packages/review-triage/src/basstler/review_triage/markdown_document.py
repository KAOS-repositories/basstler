"""
The python code blocks of a Markdown document, where they stand in it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property

CODE_BLOCK = re.compile(
    r"^(?P<fence>`{3,})(?:python[^\n]*\n|\{code-cell\}[ \t]+i?python3?\b[^\n]*\n"
    r"(?:(?::[\w-]+:[^\n]*\n)+|---[ \t]*\n.*?^---[ \t]*\n)?)"
    r"(?P<code>.*?)^(?P=fence)[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
"""
A fenced code block tagged ``python``, or a MyST notebook cell running Python after
its options, up to the fence closing it.
"""


@dataclass(frozen=True)
class MarkdownCode:
    """
    A Markdown document's python code blocks, read as one module run block after block.
    """

    text: str
    """
    The document.
    """

    @cached_property
    def module_text(self) -> str:
        """
        The document with every character outside its python code blocks blanked but
        line breaks, so that each block's code keeps its offset in the document.
        """
        characters = [
            character if character == "\n" else " " for character in self.text
        ]
        for block in CODE_BLOCK.finditer(self.text):
            start, end = block.span("code")
            characters[start:end] = self.text[start:end]
        return "".join(characters)

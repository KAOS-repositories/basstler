"""
Fenced Markdown code blocks: the languages they name and the fence around them.
"""

from __future__ import annotations

from enum import StrEnum

from basstler.class_property import classproperty

# %% languages


class CodeBlockLanguage(StrEnum):
    """
    A language a fenced Markdown code block names after its opening fence.
    """

    BASH = "bash"
    """
    Commands for bash.
    """

    @classproperty
    def fence(cls) -> str:
        """
        The run of backticks that opens and closes a code block.
        """
        return "```"

    @property
    def opening_fence(self) -> str:
        """
        The line that opens a block in this language.
        """
        return f"{CodeBlockLanguage.fence}{self}"

    def fenced(self, content: str) -> str:
        """
        >>> print(CodeBlockLanguage.BASH.fenced("ls"))
        ```bash
        ls
        ```

        :param content: The lines the block holds.
        :return: The content as a code block in this language.
        """
        return "\n".join([self.opening_fence, content, CodeBlockLanguage.fence])

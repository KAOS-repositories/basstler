"""
Text files read and written as UTF-8, whatever the locale encoding is.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

UTF_8 = "utf-8"
"""
The encoding every text is read and written in.
"""

# %% the file


@dataclass(frozen=True)
class TextFile:
    """
    A file holding text, which on Windows the locale encoding cannot encode in full.
    """

    path: Path
    """
    Where the file is.
    """

    def read(self) -> str:
        """
        :return: The file's text.
        """
        return self.path.read_text(encoding=UTF_8)

    def write(self, text: str) -> None:
        """
        Replace the file's content by *text*.
        """
        self.path.write_text(text, encoding=UTF_8)

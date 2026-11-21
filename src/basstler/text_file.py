"""
Text files read and written as UTF-8 with their line endings untouched, whatever the
platform's locale encoding and newline are.
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
        :return: The file's text, with the line endings as stored.
        """
        return self.path.read_bytes().decode(UTF_8)

    def write(self, text: str) -> None:
        """
        Replace the file's content by *text*, with its line endings as given.
        """
        self.path.write_bytes(text.encode(UTF_8))

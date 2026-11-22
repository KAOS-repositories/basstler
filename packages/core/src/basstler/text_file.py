"""
Text files read and written as UTF-8 with ``\\n`` line endings, whatever the platform's
locale encoding and newline are.
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
        :return: The file's text, every line ended by ``\\n`` however it is stored.
        """
        return self.path.read_text(encoding=UTF_8)

    def write(self, text: str) -> None:
        """
        Replace the file's content by *text*, with its line endings as given, so a file
        is written the same bytes on every platform.
        """
        self.path.write_bytes(text.encode(UTF_8))

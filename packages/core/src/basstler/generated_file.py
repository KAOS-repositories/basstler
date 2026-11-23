"""
A file whose whole text is built by the program, so it is written rather than edited.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from basstler.text_file import TextFile


class GeneratedFile(ABC):
    """
    A file that must hold exactly the text the program builds for it.
    """

    @property
    @abstractmethod
    def path(self) -> Path:
        """
        Where the file is, whether or not it exists.
        """

    @property
    @abstractmethod
    def text(self) -> str:
        """
        The text the file must hold.
        """

    def is_current(self) -> bool:
        """
        :return: Whether the file exists and holds :attr:`text`.
        """
        if not self.path.is_file():
            return False
        return TextFile(self.path).read() == self.text

    def write(self) -> None:
        """
        Write :attr:`text` to the file, replacing whatever it held.
        """
        TextFile(self.path).write(self.text)
